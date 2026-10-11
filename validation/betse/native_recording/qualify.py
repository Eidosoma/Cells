"""Offline exact whole-row qualification; explicitly not a live-memory benchmark."""

import gc
import resource
import time
from pathlib import Path

import native_row
import record_codec as codec


def rss():
    # Linux reporting, matching the registered CPU environment. VmHWM is the
    # current executable's high-water RSS. ru_maxrss can include a pre-exec peak;
    # preserve both instead of confusing either with per-row extra allocation.
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    return dict(
        current_bytes=int(fields["VmRSS"].split()[0]) * 1024,
        process_high_water_bytes=int(fields["VmHWM"].split()[0]) * 1024,
        rusage_high_water_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    )


def one(source, output, expected_sha, max_output_bytes=32 * 1024**2):
    """Read one old row, encode, fully reconstruct, compare every original field.

    Both legacy input and compatibility reconstruction are materialized. This is
    intentional independent whole-tree coverage of the partition, not a claim
    that old JSON import, this verifier, or native BETSE execution is bounded by
    the sink's 8 MiB encoded-chunk limit.
    """
    started = time.monotonic()
    codec.require(codec.file_sha(source) == expected_sha, "Legacy source checksum")
    before = rss()
    row = codec.read_json(source)
    loaded = rss()
    loaded_seconds = time.monotonic() - started
    manifest = native_row.write_row(row, output, max_output_bytes=max_output_bytes)
    written = rss()
    written_seconds = time.monotonic() - started - loaded_seconds
    restored = native_row.restore(codec.iter_records(output))
    decoded = rss()
    decoded_seconds = time.monotonic() - started - loaded_seconds - written_seconds
    original_sha, decoded_sha = codec.canonical_sha(row), codec.canonical_sha(restored)
    codec.require(original_sha == decoded_sha, "Whole native row changed")
    codec.require(codec.file_sha(source) == expected_sha, "Legacy source changed during conversion")
    sizes = [p.stat().st_size for p in Path(output).iterdir()]
    result = dict(
        status="exact_offline_row_roundtrip_not_live_qualification",
        legacy_file_sha256=expected_sha,
        canonical_sha256=original_sha,
        reconstructed_canonical_sha256=decoded_sha,
        manifest_sha256=codec.file_sha(Path(output) / "manifest.json"),
        id=row["id"],
        mode=row["mode"],
        dt_s=row["dt_s"],
        steps=row["steps"],
        source_json_bytes=Path(source).stat().st_size,
        stream_bytes=sum(sizes),
        stream_files=len(sizes),
        largest_stream_file_bytes=max(sizes),
        storage_reduction_factor=Path(source).stat().st_size / sum(sizes),
        manifest=manifest,
        memory=dict(
            before_legacy_load=before,
            after_legacy_load=loaded,
            after_write=written,
            after_full_decode=decoded,
            legacy_and_full_decode_materialized=True,
            live_observer_memory_qualified=False,
        ),
        seconds=dict(
            load=loaded_seconds,
            encode_write=written_seconds,
            decode=decoded_seconds,
            total=time.monotonic() - started,
        ),
    )
    del row, restored
    gc.collect()
    return result
