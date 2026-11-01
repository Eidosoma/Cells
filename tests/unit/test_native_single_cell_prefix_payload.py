"""Byte transport controls; no native source or numerical library execution."""

import copy
import importlib.abc
import io
import json
import struct
import sys
from pathlib import Path

import pytest

from validation.betse import native_single_cell_prefix_payload as payload


@pytest.fixture(autouse=True)
def no_science():
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    finder = Block()
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
    assert attempts == []


def column(raw):
    return dict(
        __ndarray__=True, dtype="<f8", shape=[len(raw) // 8], strides=[8], raw_bytes_hex=raw.hex()
    )


def test_dense_repeated_observations_preserve_bits_and_deduplicate(tmp_path):
    # Real default-grid matrix extent; synthetic bytes, no model/array allocation.
    raw = (bytes.fromhex("030000000000f87f") + struct.pack("<d", -0.0)) * (625 * 625 // 2)
    raw += b"\0" * 8
    assert len(raw) == 625 * 625 * 8
    value = dict(stages=[column(raw) for _ in range(20)], identity="source retained separately")
    path = tmp_path / "capture.json"
    pins = payload.write(path, value)
    assert len(pins) == 2
    assert path.stat().st_size < 20000
    decoded = payload.read(path)
    assert decoded == value
    assert decoded["stages"][0]["raw_bytes_hex"] is decoded["stages"][-1]["raw_bytes_hex"]
    metadata = payload.read(path, expand=False)
    assert metadata["stages"][0]["raw_bytes_hex"] == {payload.TOKEN: pins[1]["sha256"]}


def test_legacy_typed_json_still_reads_without_envelope(tmp_path):
    path = tmp_path / "legacy.json"
    value = {"float64_bits": "0000000000000080", "raw_bytes_hex": "030000000000f87f"}
    path.write_text(json.dumps(value))
    assert payload.read(path) == value
    assert len(payload.files(path)) == 1


@pytest.mark.parametrize("change", ["byte", "truncated", "missing", "symlink"])
def test_changed_sidecar_refuses_even_metadata_only_reads(tmp_path, change):
    path = tmp_path / "capture.json"
    pins = payload.write(path, column(bytes(payload.THRESHOLD)))
    file = path.with_name(path.name + ".arrays") / (pins[1]["sha256"] + ".bin")
    if change == "byte":
        file.write_bytes(b"x" + file.read_bytes()[1:])
    elif change == "truncated":
        file.write_bytes(b"x")
    elif change == "missing":
        file.unlink()
    else:
        target = tmp_path / "elsewhere"
        file.rename(target)
        file.symlink_to(target)
    with pytest.raises((ValueError, FileNotFoundError)):
        payload.read(path, expand=False)


@pytest.mark.parametrize(
    "change", ["unused", "duplicate", "missing", "escape", "size", "token", "misplaced"]
)
def test_incomplete_or_ambiguous_manifest_refuses(tmp_path, change):
    path = tmp_path / "capture.json"
    payload.write(path, column(bytes(payload.THRESHOLD)))
    record = json.loads(path.read_text())
    if change == "unused":
        record["payload"]["raw_bytes_hex"] = "00"
    elif change == "duplicate":
        record["blobs"].append(copy.deepcopy(record["blobs"][0]))
    elif change == "missing":
        record["blobs"] = []
    elif change == "escape":
        record["blobs"][0]["name"] = "../outside.bin"
    elif change == "size":
        record["blobs"][0]["size"] = True
    elif change == "token":
        record["payload"]["raw_bytes_hex"][payload.TOKEN] = "0" * 64
    else:
        record["payload"]["unrelated"] = record["payload"].pop("raw_bytes_hex")
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        payload.read(path)


@pytest.mark.parametrize("bound", ["MAX_BLOB", "MAX_UNIQUE", "MAX_EXPANDED"])
def test_extent_limits_apply_before_admission(tmp_path, monkeypatch, bound):
    monkeypatch.setattr(payload, bound, payload.THRESHOLD - 1)
    with pytest.raises(ValueError, match="bound"):
        payload.write(tmp_path / "capture.json", column(bytes(payload.THRESHOLD)))
    assert not (tmp_path / "capture.json").exists()


def test_expanded_limit_counts_repeated_aliases_on_read(tmp_path, monkeypatch):
    path = tmp_path / "capture.json"
    payload.write(path, [column(bytes(payload.THRESHOLD))] * 3)
    monkeypatch.setattr(payload, "MAX_EXPANDED", payload.THRESHOLD * 2)
    with pytest.raises(ValueError, match="Expanded"):
        payload.read(path, expand=False)


def test_reserved_token_untyped_objects_and_overwrite_refuse(tmp_path):
    for i, value in enumerate(({payload.TOKEN: "x"}, object(), 1.5)):
        with pytest.raises(ValueError):
            payload.write(tmp_path / str(i), value)
    path = tmp_path / "saved.json"
    payload.write(path, dict(original=True))
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        payload.write(path, dict(original=False))
    assert path.read_bytes() == before


def test_metadata_limit_and_linked_parent_remain_closed(tmp_path, monkeypatch):
    link = tmp_path / "linked"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="Linked"):
        payload.write(link / "capture.json", {})
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * (16 * 2**20 + 1))
    with pytest.raises(ValueError, match="bound"):
        payload.read(path)


def test_empty_no_blob_capture_and_noncanonical_hex(tmp_path):
    path = tmp_path / "empty.json"
    assert len(payload.write(path, dict(empty=[]))) == 1
    assert payload.read(path) == dict(empty=[])
    with pytest.raises(ValueError, match="canonical"):
        payload.write(tmp_path / "invalid.json", dict(raw_bytes_hex="AA" * payload.THRESHOLD))


@pytest.mark.parametrize("expand", [True, False])
@pytest.mark.parametrize("change", ["replacement", "growth", "second_read"])
def test_authenticate_exact_bounded_read_even_if_file_changes_after_stat(
    tmp_path, monkeypatch, expand, change
):
    path = tmp_path / "capture.json"
    raw = bytes(payload.THRESHOLD)
    pins = payload.write(path, column(raw))
    file = Path(pins[1]["path"])
    opened, sizes = [], []
    original_open = Path.open

    class Stream(io.BytesIO):
        def read(self, size=-1):
            sizes.append(size)
            return super().read(size)

    def open_file(self, *args, **kwargs):
        if self != file:
            return original_open(self, *args, **kwargs)
        opened.append(True)
        content = raw
        if change == "replacement" or (change == "second_read" and len(opened) > 1):
            content = b"x" + raw[1:]
        elif change == "growth":
            content += b"x" * 8192
        return Stream(content)

    monkeypatch.setattr(Path, "open", open_file)
    if change == "second_read":
        value = payload.read(path, expand=expand)
        if expand:
            assert value == column(raw)
    else:
        with pytest.raises(ValueError, match="changed"):
            payload.read(path, expand=expand)
    assert opened == [True] and sizes == [len(raw) + 1]
