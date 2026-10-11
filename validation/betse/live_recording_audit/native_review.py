"""D124's independent decoder applied to the actual live streams, read-only."""

import gc
from itertools import zip_longest

import audit_context as c


def inspect(label, record, original_path):
    directory = c.child(c.NATIVE, record["directory"])
    case, dt, mode = label.split("/")
    step = float(dt.removeprefix("dt_"))
    n = round(0.001 / step)
    original = c.read(original_path, None)
    c.need(
        original["id"] == case
        and original["dt_s"] == step
        and original["mode"] == mode
        and original["steps"] == n
        and record["label"] == label,
        "Native row identity",
    )
    capture = c.read(directory / "capture.json", None)
    c.need(
        c.sha(directory / "capture.json") == record["capture_sha256"]
        and c.read(directory / "comparison.json", None) == record,
        "Native capture/comparison links",
    )
    result = c.exact.inspect(original, directory / "stream")
    c.exact.Exact().match(
        capture["stream"], c.read(directory / "stream/manifest.json", None), "Live manifest"
    )
    c.need(
        capture["status"] == "live_row_captured_not_independently_qualified"
        and capture["id"] == case
        and capture["mode"] == mode
        and capture["steps"] == n
        and capture["peak_pending_updates"] == 1
        and capture["observer_horizon_lists"] is False
        and capture["native_histories_unchanged"] is True
        and capture["native_memory_bounded"] is False,
        "Live capture scope",
    )
    for name in ("observed_updates", "history_samples"):
        c.need(result[name] == capture[name] == record[name], "Native extent link")
    c.need(
        record["overlap"]["failed_comparisons"] == 0
        and record["overlap"]["common_fields_only"] is False
        and record["overlap"]["records"] == result["stream_records"],
        "Native producer overlap scope",
    )
    result |= dict(
        label=label,
        source_sha256=c.sha(original_path),
        live_manifest_sha256=c.sha(directory / "stream/manifest.json"),
        original_json_bytes=original_path.stat().st_size,
        observer_pending_peak_reported=capture["peak_pending_updates"],
        native_memory_bounded=False,
        capture_memory_counters_independently_measured=False,
    )
    del original
    gc.collect()
    return result


def pair(observed, quiet):
    """Exact comparison of shared headers, histories and endpoints, not trace-only data."""
    streams = [c.wire.Stream(observed), c.wire.Stream(quiet)]

    def common(stream):
        for value in stream:
            if value["kind"] == "native_step":
                continue
            if value["kind"] in ("native_header", "native_footer"):
                value = {k: v for k, v in value.items() if k != "trace"}
                value["row"] = {k: v for k, v in value["row"].items() if k != "mode"}
            yield value

    match, missing, count = c.exact.Exact(), object(), 0
    for left, right in zip_longest(common(streams[0]), common(streams[1]), fillvalue=missing):
        c.need(left is not missing and right is not missing, "Observer pair extent")
        match.match(left, right, "Observer pair/" + str(count))
        count += 1
    c.need(count > 0 and all(s.complete for s in streams), "Incomplete observer pair")
    return dict(
        records=count,
        exact_scalars=match.scalars,
        float64_bits=match.floats,
        negative_zero_values=match.negative_zeros,
        common_fields_only=True,
        failed_comparisons=0,
    )


def matrix_gate(rows, pairs):
    c.need(sorted(rows) == c.old.expected_labels(), "Live matrix coverage")
    c.need(sorted(pairs) == sorted({s.rsplit("/", 1)[0] for s in rows}), "Observer pair coverage")
    for label, value in rows.items():
        dt, mode = label.split("/")[1:]
        n = round(0.001 / float(dt.removeprefix("dt_")))
        c.need(
            value["status"] == "exact_every_original_value"
            and value["observed_updates"] == (n if mode == "observed" else 0)
            and value["history_samples"] == n - 1
            and value["stream_records"] == (2 * n + 1 if mode == "observed" else n + 1)
            and value["exact_scalar_comparisons"] == value["original_scalar_values"] > 0
            and value["history_array_digests"] == 9
            and value["endpoint_array_digests"] == 14,
            "Live row comparison coverage",
        )
    result = {
        k: sum(v[k] for v in rows.values())
        for k in (
            "observed_updates",
            "history_samples",
            "stream_records",
            "exact_scalar_comparisons",
            "float64_bit_comparisons",
            "negative_zero_values",
            "history_array_digests",
            "endpoint_array_digests",
        )
    }
    c.need(
        result["observed_updates"] == 6720
        and result["history_samples"] == 13404
        and result["stream_records"] == 20196,
        "Live matrix record extent",
    )
    for prefix, value in pairs.items():
        c.need(
            value["records"] == round(0.001 / float(prefix.split("dt_")[1])) + 1
            and value["failed_comparisons"] == 0
            and value["exact_scalars"] > 0,
            "Observer pair comparison coverage",
        )
    return result | dict(
        rows=len(rows),
        observer_pairs=len(pairs),
        observer_pair_scalar_comparisons=sum(p["exact_scalars"] for p in pairs.values()),
    )
