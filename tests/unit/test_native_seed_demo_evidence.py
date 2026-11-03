"""Pure typed-data paging controls; all native/model/owner entries stay blocked."""

import copy
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_seed_demo_evidence_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked multipart evidence release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def array(raw):
    return dict(
        __ndarray__=True, dtype="<f8", shape=[len(raw) // 8], strides=[8], raw_bytes_hex=raw.hex()
    )


def large_strings():
    # Nine distinct 2MiB strings exceed ordinary metadata, without numeric work.
    return [str(index) + "x" * (2 * 2**20) for index in range(9)]


def write_index(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def test_evidence_small_transport_is_exact_ordinary_format(tmp_path):
    value = dict(
        records=[["a", 1], ["b", None]],
        signed_zero=dict(float64_bits="0000000000000080"),
        failed_nan=dict(float64_bits="000000000000f87f"),
        array=array(bytes(range(256)) * 256),
    )
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    evidence.payload.write(old, value)
    evidence.capture_writer("small", new, value)
    assert old.read_bytes() == new.read_bytes()
    assert evidence.read(new) == value
    assert evidence.files(new) == evidence.payload.files(new)
    assert evidence.read(new, expand=False) == evidence.payload.read(old, expand=False)
    assert not new.with_name(new.name + ".parts").exists()


def test_evidence_real_100000_work_triples_roundtrip_exactly(tmp_path):
    value = dict(
        work=[["original/source.py", "literal_helper", i] for i in range(100000)],
        identity="a" * 64,
        source_completed=False,
        raw=array(b"\x00\x00\x00\x00\x00\x00\x00\x80" * 8192),
    )
    path = tmp_path / "ledger.json"
    pins = evidence.capture_writer("full-work-ledger", path, value)
    index = json.loads(path.read_text())
    assert index["kind"] == evidence.KIND
    assert 400000 < index["counts"]["nodes"] < evidence.MAX_NODES
    assert 1 < len(index["parts"]) <= evidence.MAX_PARTS
    assert evidence.read(path, expected_sha256=digest(path)) == value
    assert len(evidence.read(path)["work"]) == 100000
    assert pins == evidence.files(path)
    for row in index["parts"]:
        p = path.with_name(path.name + ".parts") / row["name"]
        assert digest(p) == row["sha256"]
        assert len(p.read_bytes()) <= evidence.payload.MAX_METADATA
    assert evidence.payload.MAX_NODES == 262144
    assert evidence.payload.MAX_METADATA == 16 * 2**20


def test_evidence_large_strings_preserve_sequence_order_and_exact_bytes(tmp_path):
    value = large_strings()
    path = tmp_path / "strings.json"
    evidence.write(path, value)
    result = evidence.read(path)
    assert result == value and [s[0] for s in result] == list("012345678")
    assert len(json.loads(path.read_text())["parts"]) == 10


@pytest.mark.parametrize(
    "mutation", ["missing", "changed", "duplicate", "order", "extra", "cycle", "counts", "profile"]
)
def test_evidence_manifest_and_part_corruption_refuse(tmp_path, mutation):
    value = large_strings()
    path = tmp_path / "record.json"
    evidence.write(path, value)
    index = json.loads(path.read_text())
    folder = path.with_name(path.name + ".parts")
    if mutation == "missing":
        (folder / index["parts"][0]["name"]).unlink()
    elif mutation == "changed":
        p = folder / index["parts"][0]["name"]
        raw = p.read_bytes()
        p.write_bytes(raw.replace(b"x", b"y", 1))
    elif mutation == "duplicate":
        root_part = folder / index["parts"][-1]["name"]
        record = json.loads(root_part.read_text())
        record["payload"][1] = copy.deepcopy(record["payload"][0])
        write_index(root_part, record)
        index["parts"][-1].update(sha256=digest(root_part), metadata_bytes=root_part.stat().st_size)
        write_index(path, index)
    elif mutation == "order":
        root_part = folder / index["parts"][-1]["name"]
        record = json.loads(root_part.read_text())
        record["payload"].reverse()
        write_index(root_part, record)
        index["parts"][-1].update(sha256=digest(root_part), metadata_bytes=root_part.stat().st_size)
        write_index(path, index)
    elif mutation == "extra":
        (folder / "unlisted.bin").write_bytes(b"unexpected")
    elif mutation == "cycle":
        p = folder / index["parts"][0]["name"]
        record = json.loads(p.read_text())
        record["payload"] = {evidence.REFERENCE: 0}
        write_index(p, record)
        index["parts"][0]["sha256"] = digest(p)
        index["parts"][0]["metadata_bytes"] = p.stat().st_size
        write_index(path, index)
    elif mutation == "counts":
        index["counts"]["nodes"] += 1
        write_index(path, index)
    else:
        index["profile"]["nodes"] *= 2
        write_index(path, index)
    with pytest.raises(ValueError):
        evidence.read(path)


def test_evidence_ordered_mapping_pages_and_unrelated_reference_fields(tmp_path):
    # Large mapping forces pages of explicit key/value pairs; numerical
    # reference strings and user field names remain ordinary typed data.
    value = {f"field-{i:05d}": [i, "source", "caller"] for i in range(70000)}
    value["reference"] = "opaque-native-identity"
    path = tmp_path / "mapping.json"
    evidence.write(path, value)
    result = evidence.read(path)
    assert list(result) == list(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    [
        {evidence.REFERENCE: 0},
        {evidence.PAGES: []},
        {evidence.payload.TOKEN: "a" * 64},
        [1.5],
        [object()],
        {1: "nonstring-key"},
    ],
)
def test_evidence_unsupported_or_reserved_input_refuses_before_any_write(tmp_path, value):
    path = tmp_path / "refused.json"
    with pytest.raises(ValueError):
        evidence.write(path, value)
    assert not list(tmp_path.iterdir())


def test_evidence_aggregate_depth_node_and_metadata_bounds_remain_finite(tmp_path):
    path = tmp_path / "refused.json"
    deep = None
    for _ in range(evidence.payload.MAX_DEPTH + 1):
        deep = [deep]
    with pytest.raises(ValueError, match="tree bound"):
        evidence.write(path, deep)
    with pytest.raises(ValueError, match="tree bound"):
        evidence.write(path, [None] * evidence.MAX_NODES)
    with pytest.raises(ValueError, match="metadata bound"):
        evidence.write(path, ["x" * (2**20)] * 65)
    assert not list(tmp_path.iterdir())


def test_evidence_sidecar_hash_and_global_expanded_budget_are_not_reset_by_pages(tmp_path):
    # Global limits are checked before a page exists. Repeated identical arrays
    # share unique-byte accounting but retain all expanded occurrences.
    blob = b"\x01" * (8 * 2**20)
    value = [array(blob)] * 17
    with pytest.raises(ValueError, match="Aggregate raw evidence"):
        evidence.write(tmp_path / "refused.json", value)
    assert not list(tmp_path.iterdir())


def test_evidence_global_unique_budget_is_not_per_part(tmp_path, monkeypatch):
    # Small byte-bound injection exercises distinct-digest accounting without
    # allocating nine16MiB arrays; production constants remain unchanged.
    monkeypatch.setattr(evidence.payload, "MAX_UNIQUE", 2 * evidence.payload.THRESHOLD)
    value = [array(bytes([i]) * evidence.payload.THRESHOLD) for i in range(3)]
    with pytest.raises(ValueError, match="Aggregate raw evidence"):
        evidence.write(tmp_path / "refused.json", value)
    assert not list(tmp_path.iterdir())


class FalseyError(RuntimeError):
    def __bool__(self):
        return False


def test_evidence_partial_part_write_retains_primary_cause_and_completed_files(
    tmp_path, monkeypatch
):
    value = large_strings()
    path = tmp_path / "partial.json"
    primary = FalseyError("original write error")
    primary.__cause__ = LookupError("original cause")
    original = evidence.payload.write

    def writer(p, serialized, **options):
        if p.name == "part-0001.json":
            p.with_name(p.name + ".arrays").mkdir()
            (p.with_name(p.name + ".arrays") / "partial.bin").write_bytes(b"available partial")
            raise primary
        return original(p, serialized, **options)

    monkeypatch.setattr(evidence.payload, "write", writer)
    with pytest.raises(FalseyError) as got:
        evidence.write(path, value)
    assert got.value is primary and got.value.__cause__ is primary.__cause__
    folder = path.with_name(path.name + ".parts")
    assert (folder / "part-0000.json").is_file()
    assert (folder / "part-0001.json.arrays/partial.bin").read_bytes() == b"available partial"
    assert not path.exists()
    row = json.loads((folder / "INCOMPLETE.json").read_text())
    assert len(row["completed_parts"]) == 1 and row["attempted_part"] == "part-0001.json"
    with pytest.raises(ValueError, match="overwritten"):
        evidence.write(path, value)


def test_evidence_failure_reporting_cannot_replace_original_primary(tmp_path, monkeypatch):
    value = large_strings()
    path = tmp_path / "partial.json"
    primary = FalseyError("primary")
    primary.__cause__ = KeyError("cause")
    original = evidence.snapshot.write_json

    def writer(p, serialized):
        if p.parent == path.with_name(path.name + ".parts"):
            if p.name == "INCOMPLETE.json":
                raise OSError("secondary reporter")
            raise primary
        return original(p, serialized)

    monkeypatch.setattr(evidence.snapshot, "write_json", writer)
    with pytest.raises(FalseyError) as got:
        evidence.write(path, value)
    assert got.value is primary and got.value.__cause__ is primary.__cause__
    assert any(row[0] is primary and isinstance(row[1], OSError) for row in evidence._RAW_FAILURES)
    assert not path.exists()


def small_paged_value(monkeypatch):
    """Reduced ordinary node limit exercises the same real multipart path."""
    monkeypatch.setattr(evidence.payload, "MAX_NODES", 64)
    monkeypatch.setattr(evidence, "TARGET_NODES", 16)
    return [["retained", i, "raw"] for i in range(20)]


@pytest.mark.parametrize("publication", ["partial", "complete_then_failed"])
def test_evidence_manifest_publication_failure_retains_failed_bytes(
    tmp_path, monkeypatch, publication
):
    value = small_paged_value(monkeypatch)
    baseline = tmp_path / "baseline.json"
    evidence.write(baseline, value)
    assert evidence.read(baseline) == value
    path = tmp_path / "partial.json"
    original = evidence.snapshot.write_json
    primary = FalseyError("manifest write")
    cause = primary.__cause__ = OSError("original cause")
    attempted = []

    def writer(p, serialized):
        if p == path:
            if publication == "partial":
                with p.open("xb") as stream:
                    stream.write(b'{"kind":')
            else:
                original(p, serialized)
            attempted.append(p.read_bytes())
            raise primary
        return original(p, serialized)

    monkeypatch.setattr(evidence.snapshot, "write_json", writer)
    with pytest.raises(FalseyError) as got:
        evidence.write(path, value)
    assert got.value is primary and got.value.__cause__ is cause
    assert path.read_bytes() == attempted[0]
    folder = path.with_name(path.name + ".parts")
    incomplete = json.loads((folder / "INCOMPLETE.json").read_text())
    assert len(list(folder.glob("part-*.json"))) == len(incomplete["completed_parts"])
    assert incomplete["complete"] is False and incomplete["primary_preserved"] is True
    for reader in (evidence.read, evidence.files):
        with pytest.raises(ValueError):
            reader(path, expected_sha256=digest(path))
    with pytest.raises(ValueError, match="overwritten"):
        evidence.write(path, value)


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_evidence_failure_helper_entry_rejection_retains_original_primary(
    tmp_path, monkeypatch, hook
):
    value = small_paged_value(monkeypatch)
    baseline = tmp_path / "baseline.json"
    evidence.write(baseline, value)
    assert evidence.read(baseline) == value
    path = tmp_path / "partial.json"
    primary = FalseyError("original part write")
    cause = primary.__cause__ = LookupError("original cause")
    secondary = FalseyError("actual inherited hook rejection")
    original = evidence.payload.write
    entries = []

    def writer(p, serialized, **options):
        if p.name == "part-0001.json":
            with p.open("xb") as stream:
                stream.write(b"retained failed part")
            raise primary
        return original(p, serialized, **options)

    monkeypatch.setattr(evidence.payload, "write", writer)
    previous = sys.getprofile(), sys.gettrace()
    inherited = previous[0 if hook == "profile" else 1]
    helper_code = evidence._refused.__code__
    raw_start = len(evidence._RAW_FAILURES)

    def observer(frame, event, arg):
        if event == "call" and frame.f_code is helper_code:
            entries.append((event, frame.f_locals["primary"], frame.f_locals["attempted"]))
            raise secondary
        if inherited is not None:
            return inherited(frame, event, arg)
        return None

    setter = sys.setprofile if hook == "profile" else sys.settrace
    try:
        setter(observer)
        with pytest.raises(FalseyError) as got:
            evidence.write(path, value)
    finally:
        try:
            sys.settrace(previous[1])
        finally:
            sys.setprofile(previous[0])
    assert sys.getprofile() is previous[0] and sys.gettrace() is previous[1]
    assert got.value is primary and got.value.__cause__ is cause
    assert entries == [("call", primary, "part-0001.json")]
    raw = evidence._RAW_FAILURES[raw_start:]
    assert len(raw) == 1
    assert raw[0][0] is primary and raw[0][1] is secondary
    assert raw[0][2] == "refused-boundary" and raw[0][4] == "part-0001.json"
    folder = path.with_name(path.name + ".parts")
    assert raw[0][3] == [
        dict(
            name="part-0000.json",
            sha256=digest(folder / "part-0000.json"),
            metadata_bytes=(folder / "part-0000.json").stat().st_size,
        )
    ]
    assert (folder / "part-0001.json").read_bytes() == b"retained failed part"
    assert not (folder / "INCOMPLETE.json").exists()  # Helper body never entered.
    assert not path.exists()
    for reader in (evidence.read, evidence.files):
        with pytest.raises(ValueError, match="Evidence metadata bound"):
            reader(path)


def test_evidence_read_pins_exact_input_and_rejects_symlink(tmp_path):
    path = tmp_path / "small.json"
    evidence.write(path, ["typed"])
    with pytest.raises(ValueError, match="Changed saved capture"):
        evidence.read(path, expected_sha256="0" * 64)
    linked = tmp_path / "link.json"
    linked.symlink_to(path)
    with pytest.raises(ValueError, match="Linked evidence"):
        evidence.read(linked)


def test_evidence_capture_writer_returns_only_complete_transitive_pins(tmp_path):
    value = large_strings()
    path = tmp_path / "record.json"
    pins = evidence.capture_writer("failed-prefix-work", path, value)
    assert pins[0] == dict(path=str(path), sha256=digest(path))
    assert len(pins) == 11
    assert all(digest(Path(row["path"])) == row["sha256"] for row in pins)
    assert json.loads(path.read_text())["label"] == "failed-prefix-work"
    assert evidence.read(path) == value


def bounded_parts(tmp_path):
    """Small valid multipart baseline with two separately bound raw sidecars."""
    path = tmp_path / "two-raw.json"
    folder = path.with_name(path.name + ".parts")
    folder.mkdir()
    value = [array(bytes([i]) * (40 * 2**10)) for i in (1, 2)]
    pieces = [*value, [{evidence.REFERENCE: 0}, {evidence.REFERENCE: 1}]]
    rows = []
    for index, piece in enumerate(pieces):
        part = folder / f"part-{index:04d}.json"
        evidence.payload.write(part, piece)
        rows.append(dict(name=part.name, sha256=digest(part), metadata_bytes=part.stat().st_size))
    counts, _, preview = evidence._measure(value)
    write_index(
        path,
        dict(
            kind=evidence.KIND,
            profile=evidence.PROFILE,
            label="small-valid-parts",
            root={evidence.REFERENCE: 2},
            parts=rows,
            counts=counts,
            logical_sha256=evidence._seal(preview),
        ),
    )
    assert evidence.read(path) == value
    return path, value, rows, counts


@pytest.mark.parametrize("budget", ["unique", "expanded", "nodes", "metadata"])
def test_evidence_aggregate_refusal_precedes_any_binary_authentication_or_expansion(
    tmp_path, monkeypatch, budget
):
    path, value, rows, counts = bounded_parts(tmp_path)
    calls = []
    original = evidence.payload._read

    def read(*args, **kwargs):
        calls.append(("ordinary-reader", kwargs.get("expand")))
        return original(*args, **kwargs)

    def expand(*_args):
        calls.append(("expand", True))
        pytest.fail("Global refusal happened too late")

    monkeypatch.setattr(evidence.payload, "_read", read)
    monkeypatch.setattr(evidence, "_expand", expand)
    if budget == "unique":
        monkeypatch.setattr(evidence.payload, "MAX_UNIQUE", 50 * 2**10)
    elif budget == "expanded":
        monkeypatch.setattr(evidence.payload, "MAX_EXPANDED", 50 * 2**10)
    elif budget == "nodes":
        monkeypatch.setattr(evidence, "MAX_NODES", counts["nodes"] - 1)
    else:
        monkeypatch.setattr(evidence, "MAX_METADATA", sum(r["metadata_bytes"] for r in rows) - 1)
    with pytest.raises(ValueError):
        evidence.read(path)
    assert calls == []
    assert value[0]["raw_bytes_hex"] == (bytes([1]) * (40 * 2**10)).hex()


def test_evidence_files_and_unexpanded_reads_never_construct_expanded_arrays(tmp_path, monkeypatch):
    path, _, _, _ = bounded_parts(tmp_path)

    def forbidden(*_args):
        pytest.fail("Metadata-only read expanded raw bytes")

    monkeypatch.setattr(evidence, "_expand", forbidden)
    value = evidence.read(path, expand=False)
    assert len(value) == 2 and all(
        set(v["raw_bytes_hex"]) == {evidence.payload.TOKEN} for v in value
    )
    assert len(evidence.files(path)) == 6
