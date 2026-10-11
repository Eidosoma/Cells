"""Independent wire fixtures, adversarial streams, real rows and job controls."""

import copy
import gc
import hashlib
import importlib
import json
import math
import struct
import tracemalloc
import zlib

import codec_audit_context as context
import codec_audit_job as job
import codec_review as review
import pytest
import wire_decode as wire


def u32(n):
    return n.to_bytes(4, "little")


def text_node(value):
    raw = value.encode()
    return b"s" + u32(len(raw)) + raw


@pytest.mark.parametrize(
    "payload,value",
    [
        (b"n", None),
        (b"t", True),
        (b"f", False),
        (b"i" + (-(2**63)).to_bytes(8, "little", signed=True), -(2**63)),
        (b"i" + (2**63 - 1).to_bytes(8, "little", signed=True), 2**63 - 1),
        (b"d" + struct.pack("<d", 0.0), 0.0),
        (b"d" + struct.pack("<d", -0.0), -0.0),
        (b"d" + struct.pack("<d", math.ulp(0.0)), math.ulp(0.0)),
        (b"d" + struct.pack("<d", -1.7976931348623157e308), -1.7976931348623157e308),
        (text_node("éλ\x00🧬"), "éλ\x00🧬"),
        (text_node(""), ""),
        (b"l" + u32(0), []),
        (b"m" + u32(0), {}),
        (b"D" + u32(0), []),
        (b"D" + u32(3) + struct.pack("<3d", 1.0, -0.0, 2.5), [1.0, -0.0, 2.5]),
        (b"l" + u32(3) + b"ntf", [None, True, False]),
        (
            b"m" + u32(2) + text_node("a") + b"l" + u32(1) + b"n" + text_node("b") + b"t",
            {"a": [None], "b": True},
        ),
    ],
)
def test_handwritten_wire_fixtures(payload, value):
    review.Exact().match(wire.tree(payload), value, "fixture")


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"?",
        b"nn",
        b"i\0",
        b"d\0",
        b"s" + u32(99),
        b"s" + u32(1) + b"\xff",
        b"l" + u32(2) + b"n",
        b"m" + u32(2) + b"n",
        b"D" + u32(2) + struct.pack("<d", 1.0),
        b"l" + u32(2**32 - 1),
        b"d" + struct.pack("<d", float("nan")),
        b"D" + u32(1) + struct.pack("<d", float("inf")),
        b"l\x01\0\0\0" * 65 + b"n",
        b"x" * (wire.CHUNK_BYTES + 1),
    ],
)
def test_bad_wire_refused(payload):
    with pytest.raises(ValueError):
        wire.tree(payload)


@pytest.mark.parametrize("keys", [("a", "a"), ("z", "a")])
def test_binary_map_keys_must_be_sorted_unique(keys):
    payload = b"m" + u32(2) + b"".join(text_node(k) + b"n" for k in keys)
    with pytest.raises(ValueError, match="ordered unique"):
        wire.tree(payload)


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', "NaN", "Infinity", "1e999"])
def test_nonfinite_duplicate_json_refused(text):
    with pytest.raises(ValueError):
        wire.json_value(text)


@pytest.mark.parametrize(
    "left,right",
    [
        (0.0, -0.0),
        ([0.0], [-0.0]),
        (1, 1.0),
        (True, 1),
        ([True], [1]),
        ({"a": 1}, {"b": 1}),
        ([1], [1, 2]),
        (None, False),
        (float("nan"), float("nan")),
        ([1.0], [float("inf")]),
    ],
)
def test_exact_comparison_never_coerces_types_or_signed_zero(left, right):
    with pytest.raises(ValueError):
        review.Exact().match(left, right, "changed")


def write_json(path, value):
    path.write_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )


def reseal(directory, entries):
    previous, lines = "0" * 64, []
    for entry in entries:
        entry["previous_entry_sha256"] = previous
        line = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        previous = hashlib.sha256(line).hexdigest()
        lines.append(line)
    (directory / "index.jsonl").write_bytes(b"".join(lines))
    m = wire.read_json(directory / "manifest.json")
    m["index_sha256"] = wire.sha(directory / "index.jsonl")
    m["last_entry_sha256"] = previous
    write_json(directory / "manifest.json", m)


def fixture_stream(directory, groups=None):
    # Envelope builder only: trees are handwritten bytes, never producer encoding.
    if groups is None:
        groups = [[b"n", b"d" + struct.pack("<d", -0.0)], [text_node("ok")]]
    directory.mkdir()
    entries = []
    ordinal = used = peak_record = peak_chunk = 0
    for i, group in enumerate(groups):
        raw = b"CNRS\x01\n" + b"".join(u32(len(v)) + v for v in group)
        packed = zlib.compress(raw)
        (directory / f"chunk-{i:08d}.bin.z").write_bytes(packed)
        entries.append(
            dict(
                chunk=i,
                first_record=ordinal,
                records=len(group),
                raw_bytes=len(raw),
                compressed_bytes=len(packed),
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                compressed_sha256=hashlib.sha256(packed).hexdigest(),
            )
        )
        ordinal += len(group)
        used += len(packed)
        peak_record = max(peak_record, max(map(len, group)))
        peak_chunk = max(peak_chunk, len(raw))
    m = dict(
        schema="cells.native_record_stream@1",
        records=ordinal,
        chunks=len(groups),
        payload_bytes=used,
        chunk_records=32,
        chunk_bytes=wire.CHUNK_BYTES,
        max_output_bytes=wire.STREAM_BYTES,
        index_sha256="0" * 64,
        last_entry_sha256="0" * 64,
        peak_encoded_record_bytes=peak_record,
        peak_encoded_chunk_bytes=peak_chunk,
    )
    write_json(directory / "manifest.json", m)
    reseal(directory, entries)
    return directory


def test_stream_terminal_completeness_is_explicit(tmp_path):
    directory = fixture_stream(tmp_path / "stream")
    reader = wire.Stream(directory)
    iterator = iter(reader)
    assert next(iterator) is None and reader.complete is False
    review.Exact().match(list(iterator), [-0.0, "ok"], "fixture")
    assert reader.complete is True
    with pytest.raises(ValueError, match="single-use"):
        list(reader)


def test_empty_wire_stream_is_not_native_evidence(tmp_path):
    reader = wire.Stream(fixture_stream(tmp_path / "empty", []))
    assert list(reader) == [] and reader.complete


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "linked",
        "unfinished",
        "version",
        "large_cap",
        "bool_count",
        "missing_index_line",
        "reordered_index",
        "duplicate_index",
        "broken_chain",
        "bad_index_hash",
        "bad_payload_hash",
        "truncated",
        "trailer",
        "bomb",
        "raw_hash",
        "magic",
        "short_frame",
        "zero_frame",
        "trailing_frame",
        "bad_peak",
        "negative_count",
    ],
)
def test_stream_mutants_refused_even_with_resealed_outer_hashes(tmp_path, change):
    directory = fixture_stream(tmp_path / "stream")
    chunk = directory / "chunk-00000000.bin.z"
    entries = [
        wire.json_value(line) for line in (directory / "index.jsonl").read_bytes().splitlines()
    ]
    if change == "missing":
        chunk.unlink()
    elif change == "extra":
        (directory / "orphan").touch()
    elif change == "linked":
        target = tmp_path / "outside"
        chunk.rename(target)
        chunk.symlink_to(target)
    elif change == "unfinished":
        (directory / "manifest.json").unlink()
    elif change in ("version", "large_cap", "bad_peak"):
        m = wire.read_json(directory / "manifest.json")
        if change == "version":
            m["schema"] = "future"
        elif change == "large_cap":
            m["chunk_bytes"] += 1
        else:
            m["peak_encoded_record_bytes"] += 1
        write_json(directory / "manifest.json", m)
    elif change == "bad_index_hash":
        with (directory / "index.jsonl").open("ab") as f:
            f.write(b"{}\n")
    else:
        if change == "bool_count":
            entries[0]["chunk"] = False
        elif change == "negative_count":
            entries[0]["records"] = -1
        elif change == "missing_index_line":
            entries.pop()
        elif change == "reordered_index":
            entries.reverse()
        elif change == "duplicate_index":
            entries[1] = dict(entries[0])
        elif change == "bad_payload_hash":
            entries[0]["compressed_sha256"] = "0" * 64
        elif change == "raw_hash":
            entries[0]["raw_sha256"] = "0" * 64
        elif change == "broken_chain":
            pass  # Break after resealing below, but retain the new index digest.
        else:
            raw = zlib.decompress(chunk.read_bytes())
            if change == "truncated":
                packed = chunk.read_bytes()[:-1]
            elif change == "trailer":
                packed = chunk.read_bytes() + zlib.compress(b"second stream")
            elif change == "bomb":
                packed = zlib.compress(b"x" * (wire.CHUNK_BYTES + 1))
            else:
                if change == "magic":
                    raw = b"XXXXXX" + raw[6:]
                elif change == "short_frame":
                    raw = raw[:6] + u32(10000) + raw[10:]
                elif change == "zero_frame":
                    raw = raw[:6] + u32(0) + raw[10:]
                else:
                    raw += u32(1) + b"n"
                entries[0]["raw_bytes"] = len(raw)
                entries[0]["raw_sha256"] = hashlib.sha256(raw).hexdigest()
                packed = zlib.compress(raw)
            chunk.write_bytes(packed)
            entries[0]["compressed_bytes"] = len(packed)
            entries[0]["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        reseal(directory, entries)
        if change == "broken_chain":
            rows = (directory / "index.jsonl").read_bytes().splitlines(keepends=True)
            entry = wire.json_value(rows[1])
            entry["previous_entry_sha256"] = "f" * 64
            rows[1] = json.dumps(entry).encode() + b"\n"
            (directory / "index.jsonl").write_bytes(b"".join(rows))
            m = wire.read_json(directory / "manifest.json")
            m["index_sha256"] = wire.sha(directory / "index.jsonl")
            write_json(directory / "manifest.json", m)
    with pytest.raises(ValueError):
        list(wire.Stream(directory))


def test_reader_releases_with_cyclic_gc_disabled(tmp_path):
    node = b"D" + u32(100) + struct.pack("<100d", *[1.0] * 100)
    directory = fixture_stream(tmp_path / "many", [[node] * 25 for _ in range(100)])
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        reader = wire.Stream(directory)
        assert sum(1 for _ in reader) == 2500 and reader.complete
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()
    assert peak < 2 * 1024**2


@pytest.fixture(scope="module")
def registered():
    return wire.read_json(context.CAPTURE / "registration.json", None)


def test_complete_prior_chain_and_codec_authenticate():
    with context.e.model_fence():
        r, done, files = context.authenticate()
    assert len(r["sources_sha256"]) == 14 and len(files) == 782
    assert done["rows"] == 36


@pytest.mark.parametrize(
    "module",
    [
        "record_codec",
        "native_row",
        "qualify",
        "codec_job",
        "validation.betse.native_recording",
        "cells",
        "betse",
        "numpy",
        "scipy",
        "jax",
    ],
)
def test_producer_and_models_cannot_be_imported(module):
    with context.e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(module)


@pytest.mark.parametrize("label", [n for n in context.expected_labels() if "/dt_6.25e-06/" in n])
def test_all_six_real_controls_both_modes(registered, label):
    index = context.expected_labels().index(label)
    with context.e.model_fence():
        result = job.one(index, label, registered["records"][label])
    assert result["history_samples"] == 159
    assert result["exact_scalar_comparisons"] == result["original_scalar_values"]


def test_full_real_finest_pump_leak_row(registered):
    label = "pump_leak/dt_1.5625e-06/observed"
    with context.e.model_fence():
        result = job.one(
            context.expected_labels().index(label), label, registered["records"][label]
        )
    assert result["observed_updates"] == 640 and result["stream_records"] == 1281
    assert result["negative_zero_values"] > 0
    assert result["history_array_digests"] == 9 and result["endpoint_array_digests"] == 14


@pytest.fixture(scope="module")
def tiny_native():
    # A saved eight-update fixture is only for fast semantic mutation tests. Real
    # compressed D123 evidence is exercised separately above; no encoder is used.
    original = wire.read_json(context.e.CAPTURE / "betse.json", None)["rows"]["pump_leak/observed"]
    trace, histories = original["trace"], original["histories"]
    records = [
        dict(
            kind="native_header",
            schema="cells.native_pump_row@1",
            row={k: original[k] for k in review.INITIAL},
            trace={"initial": trace["initial"]},
            histories={k: {f: v[f] for f in ("dtype", "shape")} for k, v in histories.items()},
        )
    ]
    for i in range(8):
        records.append(
            dict(
                kind="native_step",
                index=i,
                step=trace["steps"][i],
                raw_step=trace["raw_steps"][i],
                label_s=trace["labels_s"][i],
                storage=trace["storage"][i - 1] if i else None,
            )
        )
        if i:
            records.append(
                dict(
                    kind="native_history",
                    index=i - 1,
                    values={k: v["values"][i - 1] for k, v in histories.items()},
                )
            )
    records.append(
        dict(
            kind="native_footer",
            row={k: original[k] for k in review.TERMINAL},
            trace={k: trace[k] for k in review.TRACE_END},
            histories_sha256={k: v["bytes_sha256"] for k, v in histories.items()},
        )
    )
    return original, records


def test_all_original_values_are_covered(tiny_native):
    original, records = tiny_native
    result = review.compare_row(original, records)
    assert result["original_scalar_values"] == review.leaf_count(original)
    assert result["observed_updates"] == 8 and result["history_samples"] == 7


@pytest.mark.parametrize(
    "change",
    [
        "missing_header",
        "missing_footer",
        "extra_null",
        "extra_footer",
        "reordered",
        "step_index",
        "sample_index",
        "unknown_header",
        "omitted_field",
        "float_type",
        "signed_zero",
        "raw_call",
        "history_value",
        "history_shape",
        "footer_array",
        "footer_digest",
        "unknown_original",
        "omitted_original_series",
    ],
)
def test_semantic_mutations_refused(tiny_native, change):
    original, base = tiny_native
    # Copy separately to ensure that changing decoded values cannot mutate the
    # original evidence through shared synthetic-fixture references.
    row, records = copy.deepcopy(original), copy.deepcopy(base)
    if change == "missing_header":
        records.pop(0)
    elif change == "missing_footer":
        records.pop()
    elif change == "extra_null":
        records.append(None)
    elif change == "extra_footer":
        records.append(records[-1])
    elif change == "reordered":
        records[2], records[3] = records[3], records[2]
    elif change == "step_index":
        records[1]["index"] = True
    elif change == "sample_index":
        records[3]["index"] += 1
    elif change == "unknown_header":
        records[0]["row"]["unhandled"] = 7
    elif change == "omitted_field":
        del records[0]["row"]["source_constants"]
    elif change == "float_type":
        records[1]["step"]["before_elapsed_s"] = 0
    elif change == "signed_zero":
        records[1]["step"]["before_elapsed_s"] = -0.0
    elif change == "raw_call":
        records[1]["raw_step"]["calls"][0]["returned"][0][0] += 1e-20
    elif change == "history_value":
        records[3]["values"]["time"] += 1e-20
    elif change == "history_shape":
        records[0]["histories"]["time"]["shape"][0] -= 1
    elif change == "footer_array":
        records[-1]["row"]["final_arrays"]["voltage_V"]["values"][0] += 1e-12
    elif change == "footer_digest":
        records[-1]["histories_sha256"]["time"] = "0" * 64
    elif change == "unknown_original":
        row["new_field"] = None
    else:
        row["trace"]["labels_s"].pop()
    with pytest.raises(ValueError):
        review.compare_row(row, records)


def test_launch_is_detached_and_never_waits(tmp_path, monkeypatch):
    calls = []

    def register(output, tests):
        output.mkdir()
        write_json(output / "registration.json", {"test": True})

    class Child:
        pid = 456

        def __init__(self, command, **options):
            calls.append((command, options))

        def poll(self):
            raise AssertionError("No polling")

        def wait(self):
            raise AssertionError("No waiting")

    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(job.subprocess, "Popen", Child)
    output = tmp_path / "launch"
    ack = job.launch(output, None)
    assert ack["pid"] == 456 and len(calls) == 1 and ack["automatic_polling"] is False
    command, options = calls[0]
    assert options["start_new_session"] is True and options["stdin"] == job.subprocess.DEVNULL
    assert command[-2:] == ["--registration-sha", wire.sha(output / "registration.json")]


def test_registration_digest_cannot_change(tmp_path):
    write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="registration digest"):
        job.authenticate(tmp_path, "0" * 64)


def test_review_failure_is_durable_and_cannot_retry(tmp_path, monkeypatch):
    directory = tmp_path / "runs/failed"
    directory.mkdir(parents=True)
    monkeypatch.setattr(job, "ROOT", tmp_path)
    monkeypatch.setattr(job, "set_limits", lambda: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda *_: {0, 1, 2, 3})

    def fail(*_):
        raise ValueError("injected mismatch")

    monkeypatch.setattr(job, "authenticate", fail)
    with pytest.raises(ValueError, match="injected mismatch"):
        job.execute(directory, "0" * 64)
    assert (
        wire.read_json(directory / "failure.json")["status"]
        == "independent_codec_review_failed_not_closed"
    )
    assert not (directory / "completion.json").exists()
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(directory, "0" * 64)


@pytest.mark.parametrize("section", ["history", "endpoint"])
def test_array_digests_are_recomputed_not_just_copied(tiny_native, section):
    original, base = tiny_native
    row, records = copy.deepcopy(original), copy.deepcopy(base)
    if section == "history":
        row["histories"]["vm_time"]["values"][0][0] = 1.0
        records[3]["values"]["vm_time"][0] = 1.0
    else:
        row["final_arrays"]["voltage_V"]["values"][0] = 1.0
        records[-1]["row"]["final_arrays"]["voltage_V"]["values"][0] = 1.0
    # Even mutual agreement of the legacy and decoded values does not excuse an
    # inconsistent claimed array digest. These are in-memory test mutations only.
    with pytest.raises(ValueError, match="Independent " + section + " byte digest"):
        review.compare_row(row, records)


def report_fixtures():
    """Controller-only synthetic reports, never used as scientific evidence."""
    rows = {}
    for label in context.expected_labels():
        identifier, raw_dt, mode = label.split("/")
        dt = float(raw_dt.removeprefix("dt_"))
        n = round(0.001 / dt)
        rows[label] = dict(
            label=label,
            id=identifier,
            mode=mode,
            dt_s=dt,
            steps=n,
            status="exact_every_original_value",
            observed_updates=n if mode == "observed" else 0,
            history_samples=n - 1,
            stream_records=2 * n + 1 if mode == "observed" else n + 1,
            original_scalar_values=1,
            exact_scalar_comparisons=1,
            float64_bit_comparisons=1,
            negative_zero_values=0,
            history_array_digests=9,
            endpoint_array_digests=14,
            original_json_bytes=1024,
            stream=dict(
                stream_bytes=100,
                peak_chunk_bytes=80,
                peak_record_bytes=40,
                largest_stream_file_bytes=90,
            ),
        )
    captured = dict(
        rows=36,
        observed_updates=6720,
        stream_records=20196,
        stream_bytes=3600,
        max_encoded_chunk_bytes=80,
        max_encoded_record_bytes=40,
        largest_stream_file_bytes=90,
        original_native_json_bytes=36 * 1024,
    )
    return rows, captured


def test_full_matrix_gate_requires_all_rows_and_coverage():
    rows, captured = report_fixtures()
    summary = job.gate(rows, captured)
    assert summary["history_samples"] == 13404 and summary["rows"] == 36
    assert summary["history_array_digests"] == 324 and summary["endpoint_array_digests"] == 504


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "scope",
        "count",
        "coverage",
        "dtype_digest",
        "history_count",
        "byte_total",
        "peak",
    ],
)
def test_gate_rejects_incomplete_or_inconsistent_review(change):
    rows, captured = report_fixtures()
    first = rows[context.expected_labels()[0]]
    if change == "missing":
        rows.pop(context.expected_labels()[0])
    elif change == "scope":
        first["dt_s"] *= 2
    elif change == "count":
        first["observed_updates"] -= 1
    elif change == "coverage":
        first["exact_scalar_comparisons"] -= 1
    elif change == "dtype_digest":
        first["endpoint_array_digests"] -= 1
    elif change == "history_count":
        first["history_samples"] -= 1
    elif change == "byte_total":
        captured["original_native_json_bytes"] += 1
    else:
        captured["max_encoded_chunk_bytes"] += 1
    with pytest.raises(ValueError):
        job.gate(rows, captured)


def test_launch_failure_is_durable(tmp_path, monkeypatch):
    def register(output, tests):
        output.mkdir()
        write_json(output / "registration.json", {})

    def fail(*_args, **_kwargs):
        raise OSError("injected dispatch failure")

    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(job.subprocess, "Popen", fail)
    output = tmp_path / "failed_launch"
    with pytest.raises(OSError, match="injected dispatch failure"):
        job.launch(output, None)
    assert wire.read_json(output / "launch-failure.json")["status"] == "not_launched"
    assert not (output / "completion.json").exists()


def test_budget_and_existing_output_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(
        job, "BOUNDS", dict(job.BOUNDS, artifact_bytes=1024**2, free_disk_reserve_bytes=0)
    )
    with pytest.raises(ValueError, match="total budget"):
        job.budget(tmp_path)
    with pytest.raises(ValueError, match="Fresh review"):
        job.fresh(tmp_path)
