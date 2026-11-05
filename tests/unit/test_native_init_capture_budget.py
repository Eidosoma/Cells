"""Array-data/metadata controls only; no native owner or numerical solver."""

import collections
import hashlib
import json
import sys
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import pytest

from validation.betse import betse_native_membrane_initialization_archive as archive
from validation.betse import native_init_capture_budget as budget

_ARCHIVE_SNAPSHOT = archive.snapshot


@pytest.fixture(autouse=True)
def no_archive_expansion_during_preflight(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("Budget check must not call the serializer")

    monkeypatch.setattr(archive, "snapshot", refused)


def _read_bytes(value):
    raw = budget._Raw(value, budget._array_metadata(value), value.nbytes)
    blocks = list(budget._blocks(raw, np.ndarray))
    assert all(len(block) <= budget.BLOCK_BYTES for block in blocks)
    return b"".join(blocks)


@pytest.mark.parametrize(
    "form",
    ("contiguous", "transpose", "reversed", "sliced", "fortran", "scalar", "empty", "zero_dim"),
)
def test_capture_budget_logical_bytes_match_archive_for_layouts(form):
    base = np.arange(24, dtype=np.float64).reshape(4, 6)
    values = {
        "contiguous": base,
        "transpose": base.T,
        "reversed": base[::-1, ::-1],
        "sliced": base[::2, 1::2],
        "fortran": np.asfortranarray(base),
        "scalar": np.float64(-0.0),
        "empty": base[:0],
        "zero_dim": np.asarray(-0.0),
    }
    value = values[form]
    expected = value.tobytes(order="C")
    assert _read_bytes(value) == expected
    result = budget.preflight(value)
    assert result["counts"]["raw_expanded_bytes"] == len(expected)
    assert result["counts"]["raw_unique_bytes"] == len(expected)
    assert result["completed"] and not result["input_frozen"]
    assert result["actual_writer_validation_required"]


def test_capture_budget_preserves_nan_payload_signed_zero_and_different_dtypes():
    bits = np.array([0x7FF8000000001234, 0x8000000000000000, 0x7FF0000000000001], dtype=np.uint64)
    values = bits.view(np.float64)
    assert _read_bytes(values) == bits.tobytes()
    result = budget.preflight((values, bits, values.copy()))
    assert result["counts"]["raw_occurrences"] == 3
    assert result["counts"]["raw_unique_objects"] == 3
    assert result["counts"]["raw_unique_contents"] == 1
    assert result["counts"]["raw_unique_bytes"] == 24
    assert result["counts"]["raw_expanded_bytes"] == 72


def test_capture_budget_repeated_alias_expands_but_is_hashed_once():
    value = np.arange(7, dtype=np.int32)
    result = budget.preflight({"left": (value, value), "right": [value]})
    assert result["counts"]["raw_occurrences"] == 3
    assert result["counts"]["raw_unique_objects"] == 1
    assert result["counts"]["hashed_bytes"] == value.nbytes
    assert result["counts"]["raw_expanded_bytes"] == 3 * value.nbytes


def test_capture_budget_fresh_content_is_read_on_every_call():
    a = np.array([1, 2, 3], dtype=np.int64)
    b = a.copy()
    assert budget.preflight((a, b))["counts"]["raw_unique_bytes"] == a.nbytes
    b[0] = 9
    assert budget.preflight((a, b))["counts"]["raw_unique_bytes"] == 2 * a.nbytes


def test_capture_budget_plain_dataclass_namedtuple_mapping_and_object_array():
    @dataclass(frozen=True, slots=True)
    class Observation:
        cache: object
        nested: object

    Pair = collections.namedtuple("Pair", "first second")
    value = np.array([1.0, -0.0], dtype=np.float64)
    objects = np.empty((2, 2), dtype=object)
    objects[0, 0], objects[0, 1] = value, Pair(value, 2)
    objects[1, 0], objects[1, 1] = b"raw", None
    evidence = Observation(
        MappingProxyType({"array": value}),
        collections.OrderedDict(((3, objects), ("scalar", np.int32(4)))),
    )
    result = budget.preflight(evidence)
    assert result["counts"]["raw_occurrences"] == 4
    assert result["counts"]["raw_expanded_bytes"] == 3 * value.nbytes + 4
    assert result["counts"]["raw_unique_bytes"] == value.nbytes + 4


@pytest.mark.parametrize("form", ("list", "dict", "object_array", "dataclass"))
def test_capture_budget_cycles_refuse_before_any_buffer_read(monkeypatch, form):
    value = np.array([1], dtype=np.int64)
    if form == "list":
        cyclic = [value]
        cyclic.append(cyclic)
    elif form == "dict":
        cyclic = {"value": value}
        cyclic["self"] = cyclic
    elif form == "object_array":
        cyclic = np.empty(2, dtype=object)
        cyclic[0], cyclic[1] = value, cyclic
    else:

        @dataclass
        class Node:
            child: object

        cyclic = Node(None)
        cyclic.child = cyclic
    reads = []
    monkeypatch.setattr(budget, "_blocks", lambda *args: reads.append(args))
    with pytest.raises(budget.CaptureBudgetRejected, match="Cyclic"):
        budget.preflight(cyclic)
    assert reads == []


@pytest.mark.parametrize(
    "form", ("set", "opaque_mapping", "opaque_asdict", "property", "spoof_array")
)
def test_capture_budget_unknown_and_opaque_values_refuse_without_callbacks(monkeypatch, form):
    invoked = []

    class Mapping(collections.abc.Mapping):
        def __iter__(self):
            invoked.append("iter")
            raise AssertionError

        def __getitem__(self, key):
            raise AssertionError

        def __len__(self):
            raise AssertionError

    class Opaque:
        def _asdict(self):
            invoked.append("asdict")
            raise AssertionError

    @dataclass
    class WithProperty:
        value: object

    def get_value(self):
        invoked.append("property")
        raise AssertionError

    observed = WithProperty(None)
    WithProperty.value = property(get_value)
    vars(observed).clear()
    spoof = type("ndarray", (), {"__module__": "numpy", "tobytes": get_value})()
    values = {
        "set": {1},
        "opaque_mapping": Mapping(),
        "opaque_asdict": Opaque(),
        "property": observed,
        "spoof_array": spoof,
    }
    monkeypatch.setattr(budget, "_blocks", lambda *args: invoked.append("buffer"))
    with pytest.raises(ValueError):
        budget.preflight(values[form])
    assert invoked == []


@pytest.mark.parametrize("form", ("blob", "expanded", "object_nodes", "depth", "metadata"))
def test_capture_budget_oversize_metadata_refuses_before_buffer_conversion(monkeypatch, form):
    seed = np.array([7], dtype=np.uint8)
    if form == "blob":
        value = np.broadcast_to(seed, (budget.MAX_BLOB + 1,))
    elif form == "expanded":
        view = np.broadcast_to(seed, (budget.MAX_BLOB,))
        value = (view,) * (budget.MAX_EXPANDED // budget.MAX_BLOB + 1)
    elif form == "object_nodes":
        value = np.broadcast_to(np.array([None], dtype=object), (budget.MAX_NODES + 1,))
    elif form == "depth":
        value = seed
        for _ in range(budget.MAX_DEPTH + 1):
            value = [value]
    else:
        value = b"a" * (budget.MAX_METADATA // 2 + 1)
    invoked = []
    monkeypatch.setattr(budget, "_blocks", lambda *args: invoked.append(args))
    with pytest.raises(budget.CaptureBudgetRejected, match="bound"):
        budget.preflight(value)
    assert invoked == []


def test_capture_budget_exact_expanded_boundary_keeps_alias_identity():
    value = np.broadcast_to(np.array([7], dtype=np.uint8), (budget.MAX_BLOB,))
    result = budget.preflight((value,) * (budget.MAX_EXPANDED // budget.MAX_BLOB))
    assert result["counts"]["raw_unique_bytes"] == budget.MAX_BLOB
    assert result["counts"]["raw_expanded_bytes"] == budget.MAX_EXPANDED
    assert result["counts"]["hashed_bytes"] == budget.MAX_BLOB


def test_capture_budget_unique_content_limit_reads_bounded_chunks_before_refusal(monkeypatch):
    count = budget.MAX_UNIQUE // budget.MAX_BLOB
    arrays = tuple(
        np.broadcast_to(np.array([n], dtype=np.uint8), (budget.MAX_BLOB,)) for n in range(count + 1)
    )
    baseline = budget.preflight(arrays[:count])
    assert baseline["counts"]["raw_unique_bytes"] == budget.MAX_UNIQUE
    original, sizes = budget._blocks, []

    def observe(*args):
        for block in original(*args):
            sizes.append(len(block))
            yield block

    monkeypatch.setattr(budget, "_blocks", observe)
    with pytest.raises(budget.CaptureBudgetRejected, match="Unique") as caught:
        budget.preflight(arrays)
    assert max(sizes) <= budget.BLOCK_BYTES
    assert caught.value.counts["raw_unique_bytes"] == (count + 1) * budget.MAX_BLOB
    assert caught.value.counts["raw_expanded_bytes"] <= budget.MAX_EXPANDED


def test_capture_budget_real_profile_blocks_ndarray_tobytes_and_hex():
    value = np.arange(36, dtype=np.float64).reshape(6, 6)[::2, ::-1]
    previous, attempts = sys.getprofile(), []

    def guard(frame, event, argument):
        if previous is not None:
            previous(frame, event, argument)
        if event == "c_call" and (
            (
                getattr(argument, "__name__", None) == "tobytes"
                and isinstance(getattr(argument, "__self__", None), np.ndarray)
            )
            or getattr(argument, "__name__", None) == "hex"
        ):
            attempts.append(argument)
            raise AssertionError("Forbidden expanding array conversion")

    try:
        sys.setprofile(guard)
        result = budget.preflight((value, value))
    finally:
        sys.setprofile(previous)
    assert result["completed"] and not attempts and sys.getprofile() is previous


def test_capture_budget_changed_layout_between_preflight_and_read_refuses(monkeypatch):
    value = np.arange(12, dtype=np.int32)
    original = budget._blocks

    def mutate(raw, array_type):
        raw.value.shape = (3, 4)
        yield from original(raw, array_type)

    monkeypatch.setattr(budget, "_blocks", mutate)
    with pytest.raises(ValueError, match="metadata changed"):
        budget.preflight(value)


def test_capture_budget_payload_limits_remain_fixed_and_receipt_is_json_safe(monkeypatch):
    result = budget.preflight({"nan": float("nan"), "data": np.array([1, 2], dtype=np.uint8)})
    assert result["limits"]["raw_unique_bytes"] == 64 * 2**20
    assert result["limits"]["raw_expanded_bytes"] == 128 * 2**20
    assert result["limits"]["raw_blob_bytes"] == 16 * 2**20
    assert not result["owner_or_source_authority"]
    json.dumps(result, allow_nan=False)
    monkeypatch.setattr(budget.payload, "MAX_UNIQUE", budget.MAX_UNIQUE + 1)
    with pytest.raises(ValueError, match="budgets changed"):
        budget.preflight(None)


def test_capture_budget_block_digest_is_exact_for_scalar_and_strided_bits():
    value = np.array([0, 0x8000000000000000, 0x7FF8000000007654], dtype=np.uint64).view(np.float64)
    for selected in (value[::-1], value[2]):
        assert (
            hashlib.sha256(_read_bytes(selected)).digest()
            == hashlib.sha256(selected.tobytes()).digest()
        )


def test_capture_budget_extent_arithmetic_does_not_allocate_shapes():
    assert budget._extent((0, 2**100), 8) == (0, 0)
    assert budget._extent((), 8) == (1, 8)
    for shape, itemsize in (((True,), 8), ((-1,), 8), ((1,), False), ([1], 8)):
        with pytest.raises(ValueError):
            budget._extent(shape, itemsize)


def test_capture_budget_matches_actual_archive_raw_payloads_without_using_it(monkeypatch):
    @dataclass(frozen=True)
    class Row:
        values: object
        flags: object

    a = np.array([0x7FF8000000004321, 0x8000000000000000], dtype=np.uint64).view(np.float64)
    objects = np.empty(2, dtype=object)
    objects[0], objects[1] = a, np.int16(7)
    value = Row([a, a.copy(), objects], (True, None, -0.0))
    with monkeypatch.context() as local:
        local.setattr(archive, "snapshot", _ARCHIVE_SNAPSHOT)
        encoded = archive.snapshot(value)
    raw = []

    def visit(item):
        if type(item) is dict:
            for key, child in item.items():
                if key == "raw_bytes_hex":
                    raw.append(bytes.fromhex(child))
                else:
                    visit(child)
        elif type(item) is list:
            for child in item:
                visit(child)

    visit(encoded)
    result = budget.preflight(value)
    assert result["counts"]["raw_expanded_bytes"] == sum(map(len, raw))
    assert result["counts"]["raw_unique_bytes"] == sum(map(len, set(raw)))


def test_capture_budget_buffer_failure_keeps_exact_falsey_primary_and_cause(monkeypatch):
    class FalseyError(RuntimeError):
        def __bool__(self):
            return False

    primary, cause, calls = FalseyError("read refused"), OSError("cause"), []
    primary.__cause__ = cause

    def refused(*args):
        calls.append(args)
        raise primary

    monkeypatch.setattr(budget, "_blocks", refused)
    with pytest.raises(FalseyError) as caught:
        budget.preflight(np.array([1], dtype=np.uint8))
    assert caught.value is primary and primary.__cause__ is cause and len(calls) == 1
