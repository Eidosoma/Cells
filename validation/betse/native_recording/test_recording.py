"""Codec, bounded sink, failure paths and actual saved native row coverage."""

import copy
import gc
import hashlib
import importlib
import math
import struct
import tracemalloc
import zlib
from pathlib import Path

import native_row as native
import pytest
import record_codec as codec

ROOT = Path(__file__).resolve().parents[3]
SHORT = ROOT / "runs/ref-005b-pump-loop-2026-09-16/capture-01/betse.json"
VARIANTS = ["pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary"]


@pytest.fixture(scope="module")
def saved():
    return codec.read_json(SHORT)["rows"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        -(2**63),
        2**63 - 1,
        1.0,
        -0.0,
        0.0,
        math.ulp(0.0),
        -1.7976931348623157e308,
        "",
        "éλ\x00🧬",
        [],
        {},
        [1.0, -0.0, 2.5],
        [True, 1, 1.0, None],
        {"z": {"a": -0.0}, "a": [[], {}, "d", False]},
    ],
)
def test_exact_types_and_bytes(value):
    rebuilt = codec.decode(codec.encode(value))
    assert codec.canonical(value) == codec.canonical(rebuilt)
    assert type(value) is type(rebuilt)


def test_float64_is_explicit_little_endian_and_zero_sensitive():
    assert codec.encode(-0.0) == b"d" + struct.pack("<d", -0.0)
    assert codec.encode([1.0, -0.0]) == b"D\x02\0\0\0" + struct.pack("<2d", 1.0, -0.0)
    assert codec.canonical_sha(-0.0) != codec.canonical_sha(0.0)
    assert codec.canonical_sha(1) != codec.canonical_sha(1.0)
    assert codec.canonical_sha(True) != codec.canonical_sha(1)


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        [float("-inf")],
        2**63,
        -(2**63) - 1,
        (1, 2),
        b"binary",
        {1: "integer key"},
        {1, 2},
        object(),
    ],
)
def test_bad_values_refused(value):
    with pytest.raises(ValueError):
        codec.encode(value)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"x",
        b"n\0",
        b"d",
        b"s\xff\xff\xff\xff",
        b"l\xff\xff\xff\xff",
        b"D\xff\xff\xff\xff",
        b"m\x01\0\0\0n",
        b"d" + struct.pack("<d", float("nan")),
        b"D\x01\0\0\0" + struct.pack("<d", float("inf")),
        b"s\x01\0\0\0\xff",
    ],
)
def test_malformed_binary_refused(data):
    with pytest.raises((ValueError, UnicodeError)):
        codec.decode(data)


@pytest.mark.parametrize("keys", [["a", "a"], ["z", "a"]])
def test_dictionary_duplicate_or_unsorted_keys_refused(keys):
    data = b"m\x02\0\0\0" + b"".join(codec.encode(k) + b"n" for k in keys)
    with pytest.raises(ValueError, match="sorted unique"):
        codec.decode(data)


def test_depth_and_record_byte_bounds():
    value = None
    for _ in range(codec.MAX_DEPTH + 1):
        value = [value]
    with pytest.raises(ValueError, match="depth"):
        codec.encode(value)
    with pytest.raises(ValueError, match="depth"):
        codec.decode(b"l\x01\0\0\0" * (codec.MAX_DEPTH + 1) + b"n")
    with pytest.raises(ValueError, match="byte limit"):
        codec.encode([1.0] * 100, limit=64)
    with pytest.raises(ValueError, match="byte limit"):
        codec.decode(b"n" * 100, limit=64)


@pytest.mark.parametrize("data", ['{"x":1,"x":2}', '{"v":NaN}', '{"v":Infinity}', "1e999"])
def test_strict_json(data):
    with pytest.raises(ValueError):
        codec.strict_json(data)


def make_stream(directory, **limits):
    rows = [{"index": i, "values": [i / 3, -0.0]} for i in range(9)]
    with codec.RecordSink(directory, **limits) as sink:
        for row in rows:
            sink.append(row)
        manifest = sink.finish()
    return rows, manifest


@pytest.mark.parametrize(
    "limits",
    [dict(chunk_records=1), dict(chunk_records=3), dict(chunk_records=32, chunk_bytes=200)],
)
def test_chunk_boundaries_exact(tmp_path, limits):
    rows, manifest = make_stream(tmp_path / "stream", **limits)
    assert codec.canonical(rows) == codec.canonical(list(codec.iter_records(tmp_path / "stream")))
    assert manifest["peak_encoded_chunk_bytes"] <= manifest["chunk_bytes"]


def test_empty_generic_stream(tmp_path):
    with codec.RecordSink(tmp_path / "empty") as sink:
        sink.finish()
    assert list(codec.iter_records(tmp_path / "empty")) == []
    with pytest.raises(ValueError, match="footer"):
        native.restore([])


@pytest.mark.parametrize(
    "limits",
    [
        dict(chunk_records=0),
        dict(chunk_records=True),
        dict(chunk_records=33),
        dict(chunk_bytes=1),
        dict(chunk_bytes=codec.MAX_BYTES + 1),
    ],
)
def test_unregistered_capacity_refused(tmp_path, limits):
    with pytest.raises(ValueError):
        codec.RecordSink(tmp_path / "bad", **limits)
    assert not (tmp_path / "bad").exists()


def test_input_is_copied_not_retained(tmp_path):
    value = {"x": [1.0]}
    with codec.RecordSink(tmp_path / "stream") as sink:
        sink.append(value)
        value["x"][0] = 99.0
        sink.finish()
    assert list(codec.iter_records(tmp_path / "stream")) == [{"x": [1.0]}]


def test_failed_append_poison_and_partial_preserved(tmp_path):
    directory = tmp_path / "partial"
    with codec.RecordSink(directory, chunk_records=1) as sink:
        sink.append({"ok": 1})
        with pytest.raises(ValueError):
            sink.append(float("nan"))
        with pytest.raises(ValueError, match="failed sink"):
            sink.finish()
    assert (directory / "chunk-00000000.bin.z").is_file()
    assert not (directory / "manifest.json").exists()
    with pytest.raises(FileNotFoundError):
        list(codec.iter_records(directory))


def test_stream_disk_cap_checked_before_payload_write(tmp_path):
    directory = tmp_path / "quota"
    with codec.RecordSink(
        directory, chunk_records=1, max_output_bytes=codec.CONTROL_BYTES + 1
    ) as sink:
        with pytest.raises(ValueError, match="budget exhausted"):
            sink.append({"x": 1})
        with pytest.raises(ValueError, match="failed sink"):
            sink.finish()
    assert not list(directory.glob("chunk-*"))
    assert not (directory / "manifest.json").exists()


def test_context_does_not_implicitly_publish_or_overwrite(tmp_path):
    directory = tmp_path / "partial"
    with codec.RecordSink(directory) as sink:
        sink.append(None)
    assert not (directory / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        codec.RecordSink(directory)
    with pytest.raises(ValueError, match="Closed"):
        sink.append(None)


def rewrite_json(path, value):
    path.write_bytes(codec.canonical(value) + b"\n")


def reseal_index(directory, entries):
    previous = "0" * 64
    lines = []
    for entry in entries:
        entry["previous_entry_sha256"] = previous
        line = codec.canonical(entry) + b"\n"
        lines.append(line)
        previous = hashlib.sha256(line).hexdigest()
    (directory / "index.jsonl").write_bytes(b"".join(lines))
    m = codec.read_json(directory / "manifest.json")
    m["index_sha256"] = codec.file_sha(directory / "index.jsonl")
    m["last_entry_sha256"] = previous
    rewrite_json(directory / "manifest.json", m)


@pytest.mark.parametrize(
    "change",
    [
        "truncated",
        "corrupt",
        "extra",
        "missing",
        "symlink",
        "manifest_schema",
        "index_corrupt",
        "index_duplicate",
        "index_order",
        "bool_index",
        "count",
        "metric",
        "trailer",
        "bomb",
        "raw_hash",
        "magic",
        "frame_length",
        "extra_frame",
    ],
)
def test_stream_corruption_refused_even_when_outer_hashes_resealed(tmp_path, change):
    directory = tmp_path / "stream"
    make_stream(directory, chunk_records=3)
    path = directory / "chunk-00000000.bin.z"
    if change == "truncated":
        path.write_bytes(path.read_bytes()[:-1])
    elif change == "corrupt":
        data = bytearray(path.read_bytes())
        data[8] ^= 1
        path.write_bytes(data)
    elif change == "extra":
        (directory / "unexpected").touch()
    elif change == "missing":
        path.unlink()
    elif change == "symlink":
        target = tmp_path / "outside"
        path.rename(target)
        path.symlink_to(target)
    elif change in ("manifest_schema", "count", "metric"):
        m = codec.read_json(directory / "manifest.json")
        if change == "manifest_schema":
            m["schema"] += "future"
        else:
            m["records" if change == "count" else "peak_encoded_record_bytes"] += 1
        rewrite_json(directory / "manifest.json", m)
    elif change == "index_corrupt":
        with (directory / "index.jsonl").open("ab") as stream:
            stream.write(b"{}")
    else:
        entries = [
            codec.strict_json(line)
            for line in (directory / "index.jsonl").read_bytes().splitlines()
        ]
        if change == "index_duplicate":
            entries[1] = dict(entries[0])
        elif change == "index_order":
            entries.reverse()
        elif change == "bool_index":
            entries[0]["chunk"] = False
        elif change == "raw_hash":
            entries[0]["raw_sha256"] = "0" * 64
        else:
            raw = zlib.decompress(path.read_bytes())
            if change == "trailer":
                data = path.read_bytes() + b"trailing"
            elif change == "bomb":
                data = zlib.compress(b"x" * (codec.MAX_BYTES + 1))
            else:
                if change == "magic":
                    raw = b"X" + raw[1:]
                elif change == "frame_length":
                    raw = raw[: len(codec.MAGIC)] + b"\xff" * 4 + raw[len(codec.MAGIC) + 4 :]
                else:
                    raw += b"\x01\0\0\0n"
                data = zlib.compress(raw)
                entries[0]["raw_bytes"] = len(raw)
                entries[0]["raw_sha256"] = hashlib.sha256(raw).hexdigest()
            path.write_bytes(data)
            entries[0]["compressed_bytes"] = len(data)
            entries[0]["compressed_sha256"] = hashlib.sha256(data).hexdigest()
        reseal_index(directory, entries)
    with pytest.raises(ValueError):
        list(codec.iter_records(directory))


def test_writer_does_not_accumulate_horizon_index_or_payloads(tmp_path):
    # Real Python allocation measurement of the writer with generated/discarded
    # inputs; excludes legacy loading and native simulator storage by design.
    gc_was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        with codec.RecordSink(tmp_path / "bounded", chunk_bytes=32768) as sink:
            for i in range(2500):
                sink.append({"i": i, "values": [i * 0.1] * 64})
            manifest = sink.finish()
        count = sum(1 for _ in codec.iter_records(tmp_path / "bounded"))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        if gc_was_enabled:
            gc.enable()
    assert manifest["records"] == 2500
    assert manifest["peak_encoded_chunk_bytes"] <= 32768
    assert peak < 2 * 1024**2
    assert count == 2500


@pytest.mark.parametrize("mode", ["observed", "unobserved"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_all_short_rows_full_canonical_roundtrip(saved, tmp_path, variant, mode):
    row = saved[variant + "/" + mode]
    manifest = native.write_row(row, tmp_path / "row", chunk_records=3)
    rebuilt = native.restore(codec.iter_records(tmp_path / "row"))
    assert codec.canonical_sha(row) == codec.canonical_sha(rebuilt)
    assert manifest["records"] == (2 * row["steps"] + 1 if mode == "observed" else row["steps"] + 1)


@pytest.mark.parametrize(
    "change",
    [
        "unknown_field",
        "trace_field",
        "missing_step",
        "reorder_step",
        "wrong_label",
        "physical_clock",
        "pending",
        "call_return",
        "call_order",
        "sample_indices",
        "history_shape",
        "history_checksum",
        "final_checksum",
        "hook",
        "counts",
    ],
)
def test_native_corrupt_or_incomplete_rows_never_publish(saved, tmp_path, change):
    row = copy.deepcopy(saved["pump_leak/observed"])
    trace = row["trace"]
    if change == "unknown_field":
        row["new_unhandled_field"] = 1
    elif change == "trace_field":
        trace["new_unhandled_field"] = []
    elif change == "missing_step":
        trace["steps"].pop()
    elif change == "reorder_step":
        trace["steps"].reverse()
    elif change == "wrong_label":
        trace["labels_s"][0] = -0.0
    elif change == "physical_clock":
        trace["steps"][0]["after_elapsed_s"] *= 2
    elif change == "pending":
        trace["pending"] = {}
    elif change == "call_return":
        del trace["raw_steps"][0]["calls"][0]["returned"]
    elif change == "call_order":
        trace["raw_steps"][0]["calls"].reverse()
    elif change == "sample_indices":
        trace["sampled_indices"][0] = 0
    elif change == "history_shape":
        row["histories"]["time"]["shape"][0] += 1
    elif change == "history_checksum":
        row["histories"]["time"]["values"][0] *= 2
    elif change == "final_checksum":
        row["final_arrays"]["voltage_V"]["bytes_sha256"] = "0" * 64
    elif change == "hook":
        row["hook_restored"] = False
    else:
        trace["calls"]["run_return"] = 2
    with pytest.raises(ValueError):
        native.write_row(row, tmp_path / "row", chunk_records=1)
    assert not (tmp_path / "row/manifest.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        "no_footer",
        "early_footer",
        "double_footer",
        "history_order",
        "double_step",
        "double_history",
        "no_header",
    ],
)
def test_native_stream_order_and_completeness(saved, change):
    records = list(native.records(saved["pump_leak/observed"]))
    if change == "no_footer":
        records.pop()
    elif change == "early_footer":
        records.insert(1, records.pop())
    elif change == "double_footer":
        records.append(records[-1])
    elif change == "history_order":
        records[2], records[3] = records[3], records[2]
    elif change == "double_step":
        records.insert(2, records[1])
    elif change == "double_history":
        records.insert(4, records[3])
    else:
        records.pop(0)
    with pytest.raises(ValueError):
        native.restore(records)


@pytest.mark.parametrize("name", ["cells", "betse", "numpy", "scipy", "jax", "pump_native"])
def test_offline_worker_import_fence(name):
    import codec_job as job

    with job.e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


def dummy_reports():
    import codec_job as job

    result = {}
    for label in job.bind_records():
        identifier, step, mode = label.split("/")
        dt = float(step.removeprefix("dt_"))
        steps = round(0.001 / dt)
        result[label] = dict(
            id=identifier,
            dt_s=dt,
            mode=mode,
            steps=steps,
            status="exact_offline_row_roundtrip_not_live_qualification",
            canonical_sha256="a" * 64,
            reconstructed_canonical_sha256="a" * 64,
            manifest=dict(
                records=2 * steps + 1 if mode == "observed" else steps + 1,
                peak_encoded_chunk_bytes=100,
                peak_encoded_record_bytes=20,
            ),
            source_json_bytes=1000,
            stream_bytes=100,
            largest_stream_file_bytes=50,
        )
    return result


def test_exact_offline_matrix_gate():
    import codec_job as job

    summary = job.gate(dummy_reports())
    assert summary["stream_records"] == 20196
    assert summary["observed_updates"] == 6720
    assert summary["rows"] == 36


@pytest.mark.parametrize("change", ["missing", "identity", "count", "mode", "digest", "status"])
def test_offline_gate_refuses_incomplete_or_nonexact_matrix(change):
    import codec_job as job

    rows = dummy_reports()
    row = next(iter(rows.values()))
    if change == "missing":
        rows.pop(next(iter(rows)))
    elif change == "identity":
        row["id"] = "another_control"
    elif change == "count":
        row["manifest"]["records"] -= 1
    elif change == "mode":
        row["mode"] = "unobserved"
    elif change == "digest":
        row["reconstructed_canonical_sha256"] = "b" * 64
    else:
        row["status"] = "pending"
    with pytest.raises(ValueError):
        job.gate(rows)


def test_worker_requires_launch_bound_registration_digest(tmp_path):
    import codec_job as job

    codec.write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="digest changed"):
        job.authenticate(tmp_path, "0" * 64)


def test_output_quota_reserves_whole_next_stream(tmp_path, monkeypatch):
    import codec_job as job

    monkeypatch.setattr(
        job, "BOUNDS", dict(job.BOUNDS, artifact_bytes=2 * 1024**2, minimum_free_disk_bytes=0)
    )
    with pytest.raises(ValueError, match="aggregate cap"):
        job.budget(tmp_path, reserve=1024**2)


def test_probe_receipt_is_source_bound_and_complete():
    import codec_job as job

    probe = ROOT / "runs/ref-005d-codec-probe-2026-09-17/probe-02"
    receipt = job.probe_receipt(probe)
    assert receipt["completion_sha256"] == codec.file_sha(probe / "completion.json")


def test_launcher_detaches_once_without_waiting(tmp_path, monkeypatch):
    import codec_job as job

    calls = []

    def register(output, tests, probe):
        output.mkdir()
        codec.write_json(output / "registration.json", {"registered": True})

    class Child:
        pid = 12345

        def __init__(self, command, **options):
            calls.append((command, options))

        def wait(self, *_args, **_kwargs):
            raise AssertionError("Launcher must not wait")

        def poll(self):
            raise AssertionError("Launcher must not poll")

    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(job.subprocess, "Popen", Child)
    output = tmp_path / "run"
    ack = job.launch(output, None, None)
    assert len(calls) == 1 and ack["pid"] == 12345
    command, options = calls[0]
    assert options["start_new_session"] is True
    assert options["stdin"] == job.subprocess.DEVNULL
    assert command[-2:] == ["--registration-sha", codec.file_sha(output / "registration.json")]
    assert options["env"]["PYTHONNOUSERSITE"] == "1"
    assert ack["automatic_polling"] is False


def test_launch_failure_is_durable(tmp_path, monkeypatch):
    import codec_job as job

    def register(output, tests, probe):
        output.mkdir()
        codec.write_json(output / "registration.json", {})

    def fail(*_args, **_kwargs):
        raise OSError("injected launch failure")

    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(job.subprocess, "Popen", fail)
    output = tmp_path / "failed"
    with pytest.raises(OSError, match="injected"):
        job.launch(output, None, None)
    assert codec.read_json(output / "launch-failure.json")["status"] == "launch_failed"
    assert not (output / "completion.json").exists()


def test_worker_failure_never_publishes_success(tmp_path, monkeypatch):
    import codec_job as job

    output = tmp_path / "runs/failed"
    output.mkdir(parents=True)
    monkeypatch.setattr(job, "ROOT", tmp_path)
    monkeypatch.setattr(job, "set_bounds", lambda *_: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda *_: {0, 1, 2, 3})

    def fail(*_args):
        raise ValueError("injected source mismatch")

    monkeypatch.setattr(job, "authenticate", fail)
    with pytest.raises(ValueError, match="injected source mismatch"):
        job.execute(output, "0" * 64)
    assert (
        codec.read_json(output / "failure.json")["status"] == "offline_codec_failed_not_qualified"
    )
    assert not (output / "completion.json").exists()
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(output, "0" * 64)
