"""D127: authenticated carry-forward of one stopped D126 native phase."""

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live_recording"))
import live_context as ctx  # noqa: E402
import live_job as original  # noqa: E402

sys.path.insert(0, str(HERE.parent / "native_recording_audit"))
import wire_decode as wire  # noqa: E402

FAILED = ctx.ROOT / "runs/ref-005d-live-recording-2026-09-17/qualification-01"
IDENTITIES = {
    "registration.json": "3eb0443fb6818e6fca6155315e74edbf3c0e16c2713bad6d5686853bca075665",
    "failure.json": "1ba0076d91322d0011d80798ab3034a25999c3fdaf8d5fcf08a2b4bc048286ce",
    "native.json": "b16bd49c2719b83182c73cfe943b4fde984538f79c3f4748320cd7e355a7a7a2",
    "native.stderr.log": "1a062216a2011dbf1d57ac080fa739743f17d9b0a3fc5ed7f319b91219744cbf",
    "runner.stderr.log": "c7f682d4867b89f4e795f882a79ef684ccfc1cc971b3303355e2c555a46be34e",
}
NOTICE = "Ignoring cutting event, as cut profiles are disabled."
ROOT_MEMBERS = {
    "failure.json",
    "launch.json",
    "native",
    "native.json",
    "native.stderr.log",
    "native.stdout.log",
    "registration.json",
    "runner.stderr.log",
    "runner.stdout.log",
    "sources.zip",
    "started.json",
}


def native_notices(text, *, program, count):
    """Match one registered script invocation exactly; never discard arbitrary prefixes."""
    ctx.need(type(count) is int and count > 0, "Notice count must be positive")
    basename = Path(program).name
    ctx.need(basename not in ("", "-c", "-m", "-") and "\n" not in basename, "Script required")
    expected = f"[{basename}] {NOTICE}"
    ctx.need(text.splitlines() == [expected] * count, "Unexpected worker stderr")
    return dict(program=basename, message=NOTICE, count=count)


def stream_links(directory, expected):
    """Authenticate saved compressed bytes through the capture -> index -> chunk chain.

    This is a byte-integrity check of previously compared data, not a new decoder
    qualification, numerical comparison or independent physical-law review.
    """
    stream = wire.Stream(directory)
    ctx.need(stream.manifest == expected, "Capture/stream manifest changed")
    m = stream.manifest
    previous, records, chunks, size = "0" * 64, 0, 0, 0
    with (directory / "index.jsonl").open("rb") as handle:
        while line := handle.readline(wire.CONTROL_BYTES + 1):
            ctx.need(len(line) <= wire.CONTROL_BYTES and line.endswith(b"\n"), "Index line extent")
            entry = wire.json_value(line)
            ctx.need(
                entry["chunk"] == chunks < m["chunks"]
                and entry["first_record"] == records
                and entry["previous_entry_sha256"] == previous
                and type(entry["records"]) is int
                and 1 <= entry["records"] <= m["chunk_records"],
                "Index chain/coverage",
            )
            path = ctx.path_for(directory, f"chunk-{chunks:08d}.bin.z")
            ctx.need(
                path.stat().st_size == entry["compressed_bytes"]
                and ctx.sha(path) == entry["compressed_sha256"],
                "Changed compressed chunk",
            )
            previous = hashlib.sha256(line).hexdigest()
            records += entry["records"]
            chunks += 1
            size += entry["compressed_bytes"]
    ctx.need(
        (records, chunks, size, previous)
        == (m["records"], m["chunks"], m["payload_bytes"], m["last_entry_sha256"]),
        "Terminal stream coverage",
    )
    return dict(records=records, chunks=chunks, compressed_bytes=size)


def native_rows(directory, r, result):
    original.gate("native", result, r)
    ctx.need(len(result["records"]) == 36, "Native row count")
    ctx.need(
        sorted(p.name for p in (directory / "native").iterdir()) == [f"{i:02d}" for i in range(36)],
        "Native directory coverage",
    )
    updates = samples = records = chunks = 0
    for index, label in enumerate(r["native_labels"]):
        row = result["records"][label]
        ctx.need(row["label"] == label and row["directory"] == f"native/{index:02d}", "Row mapping")
        target = ctx.path_for(directory, row["directory"])
        ctx.need(ctx.sha(target / "capture.json") == row["capture_sha256"], "Capture digest")
        ctx.need(ctx.read(target / "comparison.json") == row, "Comparison receipt changed")
        captured = ctx.read(target / "capture.json")
        identifier, grid, mode = label.split("/")
        steps = round(0.001 / float(grid.removeprefix("dt_")))
        observed = steps if mode == "observed" else 0
        ctx.need(
            captured["status"] == "live_row_captured_not_independently_qualified"
            and captured["id"] == identifier
            and captured["mode"] == mode
            and captured["steps"] == steps
            and captured["observed_updates"] == row["observed_updates"] == observed
            and captured["history_samples"] == row["history_samples"] == steps - 1
            and captured["observer_horizon_lists"] is False
            and captured["native_histories_unchanged"] is True
            and captured["native_memory_bounded"] is False
            and captured["peak_pending_updates"] == 1,
            "Native lifecycle coverage",
        )
        checked = stream_links(target / "stream", captured["stream"])
        ctx.need(
            checked["records"] == row["overlap"]["records"] == steps + 1 + observed
            and row["overlap"]["common_fields_only"] is False,
            "Native record coverage",
        )
        updates += observed
        samples += steps - 1
        records += checked["records"]
        chunks += checked["chunks"]
    pairs = result["observer_pairs"]
    labels = [
        label.rsplit("/", 1)[0] for label in r["native_labels"] if label.endswith("/observed")
    ]
    ctx.need([pair["label"] for pair in pairs] == labels, "Pair coverage/order")
    for pair in pairs:
        steps = round(0.001 / float(pair["label"].split("/dt_")[1]))
        ctx.need(
            pair["common_fields_only"] is True
            and pair["exact_scalars"] > 0
            and pair["records"] == steps + 1
            and pair["failed_comparisons"] == 0,
            "Pair record coverage",
        )
    ctx.need((updates, samples, records) == (6720, 13404, 20196), "Native totals")
    return dict(
        native_runs=36,
        observer_pairs=18,
        observed_updates=updates,
        history_samples=samples,
        stream_records=records,
        compressed_chunks=chunks,
    )


def failed_packet():
    """Only this exact logging failure is reusable; the original remains failed."""
    ctx.hashes(FAILED, IDENTITIES)
    ctx.need({p.name for p in FAILED.iterdir()} == ROOT_MEMBERS, "Unexpected stopped-run members")
    files = ctx.inventory(FAILED)
    ctx.need(len(files) == 964, "Stopped-run inventory extent")
    r = original.authenticate(FAILED, IDENTITIES["registration.json"])
    ctx.need(len(r["sources_sha256"]) == 668, "Original source coverage")
    ctx.need(
        ctx.read(FAILED / "launch.json")["registration_sha256"] == IDENTITIES["registration.json"],
        "Original launch binding",
    )
    failure = ctx.read(FAILED / "failure.json")
    ctx.need(
        failure["status"] == "live_window_qualification_failed"
        and failure["automatic_retry"] is False
        and failure["traceback"].endswith("ValueError: Unexpected worker stderr\n"),
        "Not the known controller-only failure",
    )
    notices = native_notices(
        (FAILED / "native.stderr.log").read_text(), program=ctx.HERE / "live_job.py", count=72
    )
    result = ctx.read(FAILED / "native.json")
    coverage = native_rows(FAILED, r, result)
    ctx.need(ctx.inventory(FAILED) == files, "Stopped packet changed during verification")
    return dict(
        directory=str(FAILED.relative_to(ctx.ROOT)),
        files_sha256=files,
        identities=IDENTITIES,
        source_inputs=668,
        known_notices=notices,
        **coverage,
        artifact_bytes=sum((FAILED / name).stat().st_size for name in files),
        original_stays_failed=True,
        new_native_runs=0,
        independent_live_review_complete=False,
    )


def sources():
    names = set(ctx.sources())
    names.update(str(p.relative_to(ctx.ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".md"))
    names.add("reports/REF005D_LIVE_CONTINUATION_HANDOFF.md")
    return {name: ctx.sha(ctx.ROOT / name) for name in sorted(names)}
