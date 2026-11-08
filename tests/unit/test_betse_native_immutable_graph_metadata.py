"""Stdlib synthetic controls; original producer/serializer source is compile-only."""

import ast
import builtins
import hashlib
import json
import os
import struct
import sys
import time
import tracemalloc
from pathlib import Path
from types import MappingProxyType

import pytest

from cells.processes import betse_native_immutable_graph_metadata as metadata

ROOT = Path(__file__).resolve().parents[2]
PRODUCER = "src/cells/processes/betse_native_parameter_yaml_graph.py"
ORIGINAL = "src/cells/processes/betse_normal_current.py"


@pytest.fixture(autouse=True)
def blocked(monkeypatch, tmp_path):
    """No native modules, arrays, parameter owners, RNG or operator execution."""
    attempts, prior, trace = [], sys.getprofile(), sys.gettrace()
    importer = builtins.__import__

    def importing(name, *args, **kwargs):
        if name.split(".")[0] in ("betse", "numpy", "scipy"):
            attempts.append(("import", name))
            raise AssertionError("Native/numerical imports are held")
        return importer(name, *args, **kwargs)

    def profile(frame, event, arg):
        name = frame.f_globals.get("__name__", "")
        if event == "call" and (
            name.split(".")[0] in ("betse", "numpy", "scipy")
            or name.startswith("cells.processes.")
            and name != metadata.__name__
        ):
            attempts.append(("entry", name, frame.f_code.co_name))
            raise AssertionError("Native/owner/source bodies are held")
        if prior is not None:
            prior(frame, event, arg)

    monkeypatch.setattr(builtins, "__import__", importing)
    try:
        sys.setprofile(profile)
        yield
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                {
                    "attempts": attempts,
                    "profile_restored": sys.getprofile() is prior,
                    "trace_restored": sys.gettrace() is trace,
                    "native_owner_or_numerical_credit": False,
                },
                sort_keys=True,
            )
        )
        assert not attempts


def graph_descriptor():
    return {
        "roots": [("_conf", ("ref", 0)), ("height", ("ref", 3))],
        "nodes": [
            {"token": 0, "type": "builtins.dict", "dict_storage": [(("ref", 1), ("ref", 2))]},
            {"token": 1, "type": "str", "value": "same\ud800\U0001f9ec"},
            {"token": 2, "type": "builtins.list", "list_storage": [("ref", 3), ("ref", 3)]},
            {"token": 3, "type": "float", "float64": "8000000000000000"},
            {"token": 4, "type": "bytes", "bytes": "00ff01"},
            {"token": 5, "type": "int", "value": -(2**80)},
        ],
        "scalar_bytes": 19,
        "additional": {"null": None, "bools": [False, True], "empty": ({}, [], ())},
    }


def original_bytes(descriptor):
    # In this closed no-float/no-array domain, JSON already performs the original
    # record() tuple/list projection. No original module or source body executes.
    return json.dumps(descriptor, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def test_real_producer_and_serializer_are_compile_only_with_known_metadata_domain():
    producer, original = (ROOT / PRODUCER).read_bytes(), (ROOT / ORIGINAL).read_bytes()
    assert hashlib.sha256(original).hexdigest() == metadata_original_sha()
    compile(producer, str(ROOT / PRODUCER), "exec", dont_inherit=True)
    compile(original, str(ROOT / ORIGINAL), "exec", dont_inherit=True)
    capture = next(n for n in ast.parse(producer).body if isinstance(n, ast.FunctionDef))
    assert capture.name == "capture"
    text = ast.unparse(capture)
    assert 'node["float64"]' not in text  # ast.unparse uses single-quoted keys.
    assert "node['float64'] = struct.pack('>d', value).hex()" in text
    assert "node['bytes'] = value.hex()" in text
    serializer = next(n for n in ast.parse(original).body if getattr(n, "name", None) == "record")
    assert "isinstance(value, (tuple, list))" in ast.unparse(serializer)
    assert "return [record(item) for item in value]" in ast.unparse(serializer)


def metadata_original_sha():
    return "294a4d3e267e9d75caccd50eaaacc462931a8597d5eadd88ea94f9dc3856add7"


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, -19, 2**100, "", 'x\n\t"\\', "\ud800\udfff\U0001f9ec", [], (), {}],
)
def test_exact_canonical_bytes_hash_and_export(value):
    descriptor, raw = {"value": value}, (object(), object())
    result = metadata.freeze_graph((raw, descriptor))
    expected = original_bytes(descriptor)
    assert result.raw_objects is raw
    assert result.descriptor_bytes == expected
    assert result.descriptor_sha256 == hashlib.sha256(expected).hexdigest()
    assert metadata.export_descriptor(result) == json.loads(expected)


def test_full_descriptor_preserves_tokens_order_aliases_and_all_scalar_bits():
    descriptor = graph_descriptor()
    # Float payloads are already strings from the real graph producer; never
    # reconstructed as floating-point numbers by the immutable representation.
    descriptor["bits"] = [
        struct.pack(">d", struct.unpack(">d", bytes.fromhex(bits))[0]).hex()
        for bits in ("8000000000000000", "7ff0000000000000", "7ff8000000000001")
    ]
    shared = ["same", ("ref", 3)]
    descriptor["left"] = descriptor["right"] = shared
    raw = (object(), shared, shared)
    image = metadata.freeze_graph((raw, descriptor))
    assert image.raw_objects is raw and image.raw_objects[1] is image.raw_objects[2]
    assert image.descriptor_bytes == original_bytes(descriptor)
    assert metadata.export_descriptor(image)["bits"] == descriptor["bits"]


def test_image_has_no_mutable_descriptor_backing_and_exports_are_independent():
    descriptor = graph_descriptor()
    raw = (object(),)
    image = metadata.freeze_graph((raw, descriptor))
    wire = image.descriptor_bytes
    first, second = metadata.export_descriptor(image), metadata.export_descriptor(image)
    first["nodes"][0]["token"] = 99
    descriptor["nodes"][0]["token"] = 100
    assert second["nodes"][0]["token"] == 0
    assert image.descriptor_bytes is wire and image.raw_objects is raw
    assert type(image.descriptor_bytes) is bytes and type(image.descriptor_sha256) is str
    assert not hasattr(image, "__dict__")
    with pytest.raises(AttributeError):
        image.descriptor_bytes = b"{}"
    with pytest.raises(AttributeError):
        object.__setattr__(image, "descriptor_bytes", b"{}")
    # The producer's detached image is past metadata. A changed live graph must
    # be captured/compared by its owner; old mutable views are never authority.
    assert metadata.freeze_graph((raw, descriptor)).descriptor_sha256 != image.descriptor_sha256


@pytest.mark.parametrize("retarget", ["image", "equal_image", "raw_tuple", "equal_raw", "subclass"])
def test_retained_image_or_reference_retarget_refuses(retarget):
    raw = (object(), object())
    image = metadata.freeze_graph((raw, graph_descriptor()))
    actual, objects = image, raw
    if retarget == "image":
        actual = metadata.freeze_graph((raw, {"other": 1}))
    elif retarget == "equal_image":
        actual = metadata.FrozenGraph(*image)
        assert actual == image and actual is not image
    elif retarget in ("raw_tuple", "equal_raw"):
        objects = tuple(list(raw)) if retarget == "equal_raw" else (object(),)
    else:

        class Subclass(metadata.FrozenGraph):
            pass

        actual = Subclass(*image)
    with pytest.raises(ValueError, match="Exact retained"):
        metadata.require_retained(actual, retained_image=image, retained_objects=objects)
    assert metadata.require_retained(image, retained_image=image, retained_objects=raw) is image


class EqualityTrap(type):
    def __eq__(cls, other):
        raise AssertionError("No user metaclass equality")

    __hash__ = type.__hash__


class Unsupported(metaclass=EqualityTrap):
    def __repr__(self):
        raise AssertionError("No user repr")


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -0.0,
        float("nan"),
        b"raw",
        bytearray(b"raw"),
        {1, 2},
        MappingProxyType({}),
        Unsupported(),
    ],
    ids=["float", "signed_zero", "nan", "bytes", "bytearray", "set", "proxy", "user_object"],
)
def test_unsupported_exact_types_refuse_and_retain_raw_failure(value):
    graph = ((object(),), {"value": value})
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_graph(graph)
    error = caught.value
    assert error.graph is graph and error.raw_objects is graph[0] and error.descriptor is graph[1]
    assert error.source_error is error.__cause__ and error.stage == "immutable_tree"


@pytest.mark.parametrize("base", [str, int, list, tuple, dict])
def test_scalar_container_and_key_subclasses_refuse_without_user_conversion(base):
    class Subclass(base):
        def __iter__(self):
            raise AssertionError("No user iterator")

        def __str__(self):
            raise AssertionError("No user conversion")

    value = Subclass("x") if base is str else Subclass()
    with pytest.raises(metadata.MetadataRejected):
        metadata.freeze_graph(((), {"value": value}))
    if base is str:
        with pytest.raises(metadata.MetadataRejected):
            metadata.freeze_graph(((), {value: 1}))


@pytest.mark.parametrize("kind", ["list", "dict", "indirect"])
def test_cycles_refuse_with_exact_raw_graph_retained(kind):
    value = [] if kind != "dict" else {}
    if kind == "list":
        value.append(value)
    elif kind == "dict":
        value["self"] = value
    else:
        value.append((value,))
    graph = ((value,), {"cycle": value})
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_graph(graph)
    assert "Cyclic" in str(caught.value.source_error)
    assert caught.value.graph is graph and caught.value.raw_objects[0] is value


@pytest.mark.parametrize(
    "descriptor,limits",
    [
        ({"x": [1] * 8}, (8, 10, 100)),
        ({"x": [[[1]]]}, (30, 2, 100)),
        ({"x": "\\" * 20}, (30, 10, 30)),
        ({"x": 2**200}, (30, 10, 16)),
    ],
)
def test_explicit_node_depth_scalar_and_encoded_byte_bounds(descriptor, limits):
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_graph(((), descriptor), limits=limits)
    assert "bound" in str(caught.value.source_error)


@pytest.mark.parametrize("limits", [[3, 3, 3], (True, 3, 3), (3, 0, 3), (3, 3, -1), (3, 129, 3)])
def test_invalid_limits_refuse_before_tree(limits, monkeypatch):
    monkeypatch.setattr(metadata, "_tree", lambda *args: pytest.fail("Tree must not run"))
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_graph(((), {}), limits=limits)
    assert caught.value.stage == "input"


@pytest.mark.parametrize("change", ["root", "nested", "equal_retarget", "append", "delete"])
def test_mid_capture_mutation_refuses_before_publication(change):
    descriptor = {"nested": [object.__name__, [1, 2]], "other": 9}
    graph, prior, attempts = ((object(),), descriptor), sys.getprofile(), []

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code is metadata._encode.__code__ and not attempts:
            attempts.append(change)
            if change == "root":
                descriptor["other"] = 10
            elif change == "nested":
                descriptor["nested"][1][0] = 8
            elif change == "equal_retarget":
                descriptor["nested"] = list(descriptor["nested"])
            elif change == "append":
                descriptor["nested"].append(7)
            else:
                descriptor.pop("other")

    try:
        sys.setprofile(profile)
        with pytest.raises(metadata.MetadataRejected) as caught:
            metadata.freeze_graph(graph)
    finally:
        sys.setprofile(prior)
    assert caught.value.stage == "capture_recheck" and caught.value.graph is graph
    assert attempts == [change]


class FalseyError(RuntimeError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("point", ["_tree", "_encode", "_unchanged"])
def test_original_falsey_observer_error_cause_and_partial_retained(point):
    graph, prior = ((object(),), graph_descriptor()), sys.getprofile()
    primary, cause = FalseyError("observer"), KeyError("original")
    code = getattr(metadata, point).__code__

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code is code:
            raise primary from cause

    try:
        sys.setprofile(profile)
        with pytest.raises(metadata.MetadataRejected) as caught:
            metadata.freeze_graph(graph)
    finally:
        sys.setprofile(prior)
    assert caught.value.source_error is caught.value.__cause__ is primary
    assert primary.__cause__ is cause and caught.value.graph is graph
    if point == "_unchanged":
        assert type(caught.value.partial[1]) is bytes


def test_repeated_retained_use_never_reencodes_or_rehashes(monkeypatch):
    raw = (object(),)
    image = metadata.freeze_graph((raw, graph_descriptor()))

    def forbidden(*args, **kwargs):
        pytest.fail("Historical retained use must not serialize or rehash")

    monkeypatch.setattr(metadata, "_tree", forbidden)
    monkeypatch.setattr(metadata, "_encode", forbidden)
    monkeypatch.setattr(metadata.hashlib, "sha256", forbidden)
    for _ in range(30):
        result = metadata.require_retained(image, retained_image=image, retained_objects=raw)
        assert result.descriptor_sha256 is image.descriptor_sha256


@pytest.mark.parametrize("graph", [None, [], ([], {}), ((), []), ((), {}, None)])
def test_malformed_capture_refuses_without_normalizing_raw_inputs(graph):
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_graph(graph)
    assert caught.value.graph is graph and caught.value.stage == "input"


def test_wire_length_boundary_and_empty_containers_are_exact():
    graph = ((), {"x": [[], {}, None]})
    expected = original_bytes(graph[1])
    image = metadata.freeze_graph(graph, limits=(40, 8, len(expected)))
    assert image.descriptor_bytes == expected
    with pytest.raises(metadata.MetadataRejected):
        metadata.freeze_graph(graph, limits=(40, 8, len(expected) - 1))


@pytest.mark.parametrize("kind", ["many_fragments", "large_payload"])
def test_large_encoder_preserves_bytes_without_retaining_all_fragments(kind, tmp_path):
    descriptor = {
        "values": list(range(120_000)) if kind == "many_fragments" else ["x" * 1024] * 8192
    }
    expected = original_bytes(descriptor)
    tree, _ = metadata._tree(descriptor, metadata.DEFAULT_LIMITS)
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        actual = metadata._encode(tree, metadata.MAX_BYTES)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    budget = max(4 * 2**20, len(expected) * 3 // 2 + 2**20)
    assert type(actual) is bytes and actual == expected
    assert peak < budget
    (tmp_path / "encoding-memory.json").write_text(
        json.dumps(
            dict(
                corpus=kind,
                payload_bytes=len(actual),
                payload_sha256=hashlib.sha256(actual).hexdigest(),
                encoder_peak_traced_bytes=peak,
                maximum_traced_bytes=budget,
                scope="encoder allocations only; input tree and expected bytes preexist",
                actual_native_graph_or_whole_run_credit=False,
            ),
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("point", ["write", "getvalue"])
def test_buffer_allocation_failure_preserves_primary_and_never_publishes(point, monkeypatch):
    class FalseyMemoryError(MemoryError):
        def __bool__(self):
            return False

    primary, cause = FalseyMemoryError("buffer allocation"), OSError("allocation cause")
    graph = ((object(),), graph_descriptor())
    factory, before = metadata.BytesIO, dict(metadata._HISTORY_ISSUED)

    class Buffer:
        def __init__(self):
            self.buffer = factory()

        def write(self, value):
            if point == "write":
                raise primary from cause
            return self.buffer.write(value)

        def getvalue(self):
            raise primary from cause

    monkeypatch.setattr(metadata, "BytesIO", Buffer)
    with pytest.raises(metadata.MetadataRejected) as caught:
        metadata.freeze_history_graph(graph)
    assert caught.value.source_error is caught.value.__cause__ is primary
    assert primary.__cause__ is cause
    assert caught.value.graph is graph and caught.value.raw_objects is graph[0]
    assert caught.value.stage == "canonical_bytes" and caught.value.partial[1] is None
    assert metadata._HISTORY_ISSUED == before


def _measure(destination):
    """Bounded synthetic comparison; not a whole-phase speedup prediction."""
    if os.sched_getaffinity(0) != {3}:
        raise ValueError("CPU3 required for isolated metadata measurement")
    corpus = graph_descriptor()
    corpus["synthetic_rows"] = [
        {"token": i, "storage": [("ref", j) for j in range(8)], "type": "builtins.list"}
        for i in range(512)
    ]
    raw = (object(),)
    began = time.perf_counter_ns()
    image = metadata.freeze_graph((raw, corpus))
    freeze_ns = time.perf_counter_ns() - began
    expected = hashlib.sha256(original_bytes(corpus)).hexdigest()
    assert image.descriptor_sha256 == expected
    samples = []
    for repeat in range(7):
        operations = ("fresh_json_hash", "fresh_freeze", "retained_immutable")
        for operation in operations if repeat % 2 == 0 else reversed(operations):
            began = time.perf_counter_ns()
            for _ in range(20):
                if operation == "fresh_json_hash":
                    value = hashlib.sha256(original_bytes(corpus)).hexdigest()
                elif operation == "fresh_freeze":
                    value = metadata.freeze_graph((raw, corpus)).descriptor_sha256
                else:
                    value = metadata.require_retained(
                        image, retained_image=image, retained_objects=raw
                    ).descriptor_sha256
                assert value == expected
            samples.append(
                {
                    "operation": operation,
                    "repeat": repeat,
                    "calls": 20,
                    "wall_ns": time.perf_counter_ns() - began,
                }
            )
    (destination / "measurement.json").write_text(
        json.dumps(
            {
                "source_sha256": hashlib.sha256(Path(metadata.__file__).read_bytes()).hexdigest(),
                "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "one_time_freeze_ns": freeze_ns,
                "payload_bytes": len(image.descriptor_bytes),
                "samples": samples,
                "baseline": "direct JSON/hash only; excludes generic record tree",
                "scope": "synthetic immutable representation, not integrated owner validation",
                "native_owner_or_numerical_credit": False,
            },
            sort_keys=True,
            indent=2,
        )
    )


def measure(destination):
    destination = Path(destination)
    destination.mkdir()
    patches = pytest.MonkeyPatch()
    blockade = blocked.__wrapped__(patches, destination)
    next(blockade)
    try:
        _measure(destination)
    finally:
        try:
            next(blockade)
        except StopIteration:
            pass
        finally:
            patches.undo()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", required=True)
    measure(parser.parse_args().measure)
