# Lossless native evidence recording — R0, first implementation

2026-09-17, D123. This is a **validation-side storage layer**, not a change to
Cells, BETSE, numerical tolerances or the accepted 1 ms pilot. It implements the
first stage of the [longer-duration plan](../../../docs/BETSE_PUMP_RELAXATION_PLAN.md).
The full offline matrix must finish and be reviewed before a separately
registered live observer replay. Nothing here qualifies a longer trajectory.

## Separation of responsibilities

- `record_codec.py`: generic, bounded record encoding, chunk sink and iterator.
- `native_row.py`: explicit pump INIT evidence layout and structural validation.
- `qualify.py`: deliberately materialized, exact whole-row legacy round-trip.
- `codec_job.py`: source-bound registration, resource limits and detached execution.
- `test_recording.py`: byte/type, malformed evidence, memory and controller checks.

No simulator, array library, frozen producer or numerical reference is imported.
Source authentication reuses read-only evidence helpers under an import fence.
The old archives, including the rejected pilot, remain untouched. This is not
an independent scientific re-audit: it checks lossless preservation of evidence
whose numerical meaning was separately reviewed under D120.

## On-disk contract

Each stream is a fresh directory containing `chunk-NNNNNNNN.bin.z`, an
append-only `index.jsonl`, and a final `manifest.json`. No overwrite/resume API
exists. Partial directories remain evidence of incomplete work, not successful
runs. A caught append failure poisons the writer; context-manager exit never
implicitly publishes success.

The raw chunk begins with six bytes `CNRS\x01\n`. Each record is prefixed by its
unsigned little-endian 32-bit encoded length. Each complete chunk is compressed
with zlib, level 6. Compression is lossless; there is no quantization, decimal
rounding, sparse time sampling or deletion of physical boundary records.

The tree encoding distinguishes all supported JSON types:

| Tag | Payload |
| --- | --- |
| `n`, `t`, `f` | Null, true, false; no payload |
| `i` | Signed little-endian 64-bit integer |
| `d` | IEEE little-endian float64, including the sign of zero |
| `s` | Unsigned 32-bit byte length, then strict UTF-8 |
| `l` | Unsigned 32-bit element count, then individually typed children |
| `D` | Unsigned 32-bit element count, then homogeneous float64 values |
| `m` | Unsigned 32-bit pair count, then string keys/typed values; keys sorted and unique |

No executable tags, object constructors or pickle payloads are accepted. The
codec rejects unsupported types, out-of-int64 integers, nonfinite numbers,
duplicate keys, invalid UTF-8, excessive nesting/length, truncated or trailing
data, and incompatible versions. It preserves numeric type as well as value:
`1`, `1.0`, `true`, `0.0` and `-0.0` are not interchangeable. Dictionary insertion
order, original indentation and whitespace are not part of canonical JSON
identity; every original key, nested value and numeric sign is.

Each index entry binds the chunk ordinal, first record/count, raw/compressed
sizes and SHA-256 digests, and the previous index entry's digest. The manifest
binds the whole index, terminal chain, total records/chunks/bytes and measured
encoded-buffer maxima. Readers check deterministic membership, sequence,
compression extent, digests and declared bounds. Consumers must **exhaust** the
iterator to establish terminal completeness. A partial read is not acceptance.

The writer flushes/fsyncs a chunk before its index entry and publishes the
manifest last with an exclusive link. A missing/torn payload, orphan file,
unfinished manifest or incompatible schema is refused. Hashes establish
integrity only relative to the externally bound registration/completion; they
are not a digital signature or a biological validity claim.

## A layout that can later stream live evidence

The pump-row schema is `cells.native_pump_row@1`, contained in
`cells.native_record_stream@1` streams:

1. Initial metadata: geometry, preparation, constants, ownership/layout,
   expected history shapes and initial physical observation.
2. Ordered physical-update records, preserving the complete old step and raw
   call arguments/returns, raw sample label, physical times and storage event.
3. History samples interleaved after their corresponding completed updates;
   unobserved rows contain histories but no invented physical-update trace.
4. A terminal record with final arrays, endpoint, fixture/hook closure and the
   completed histories' float64-byte hashes.

The header does not require final hashes or endpoint state before integration.
Semantic validation retains only fixed metadata, counters and running array
hashes. It rejects incomplete calls, missing/reordered updates/history samples,
wrong clocks, changed array extents/checksums and incomplete lifecycle closure.
It does not replace the separate physical-law/conservation/energy audit.

This adapter deliberately supports the closed pump INIT layout, not arbitrary
BETSE output. Every original top-level/trace field is accounted for; unhandled
schema additions are rejected. Native pickle paths are retained as data, and
the prior authenticated archive binds the actual pickle bytes. They are never
loaded or presented as qualified native restarts.

The live observer is **not implemented by this change**. It must deliver and
release records at real update/storage boundaries, preserve observation
neutrality, and handle BETSE's internal histories explicitly. Appending a final
chunked file to the old accumulating observer would not satisfy that gate.

## Bounds and measurements

The initial sink permits at most **32 records / 8 MiB encoded bytes per chunk**,
whichever limit is reached first. Interleaved step/history records make this
stricter than the proposed maximum of 32 physical updates. Headers and terminal
records also count; an individual oversized record is rejected, not split or
silently accepted. Buffers and index entries are released incrementally, even
with Python cyclic garbage collection disabled.

This is **not an 8 MiB process-RAM claim**. Compression workspace, temporary
buffers, Python object overhead, caller-owned inputs and decoded objects are
additional. Tests measure writer/iterator allocations on 2,500 generated records
with cyclic GC disabled; the resource probe separately records real encoded
buffer lengths and Linux RSS. `VmHWM` and `ru_maxrss` are both retained because
the latter can include a pre-exec high-water mark.

Offline qualification intentionally loads one old JSON row and reconstructs one
complete decoded row. Comparing their independent canonical JSON digests
checks the entire partition/reconstruction, including every nested field and
signed zero. Neither this legacy importer nor `restore()` is a bounded-memory
live consumer. No horizon-length record/index list is retained by the sink or
streaming iterator themselves.

The largest-row probe uses the 640-update pump+leak record. Both preserved probes
converted **143,185,735 bytes** into **1,549,225 bytes** (about **92.4× smaller**),
with a **1,087,999-byte** largest encoded chunk and **38,726-byte** largest
compressed file. The final source-bound probe took **38.519 s** including
legacy load, encoding, full reconstruction and two canonical digests. Its
process high-water RSS was **504.82 MiB**; this is dominated by the deliberately
materialized old JSON/reconstructed trees, not an 8 MiB live-memory result.
Compression is measured evidence storage, not simulator or GPU performance.

The full offline campaign is separately bounded to CPUs 0–3, **900 seconds**,
**4 GiB address space**, **16 MiB/file**, **32 MiB/stream**, **512 MiB aggregate**
and a **1 GiB free-disk reserve**. The controller reserves the entire next
stream's allowance before starting it; the sink checks its own output quota
before writing a chunk. These are engineering safety caps, not expected use or
approved limits for a live/longer simulation. The source-bound probe justifies
trying this matrix; a limit failure remains a failed attempt, not an auto-retry.

## Execution and next gates

The registered matrix converts all **36** saved D119 native rows: eighteen
observed/unobserved pairs, **6,720 observed updates**, **13,404 history samples**
and **20,196 stream records**, including headers and terminal records. Whole-row
canonical reconstruction is required for each row; short fixture tests alone
cannot close the matrix.

**132 software checks pass in 3.51 s**, including the allocation test below
2 MiB on its small generated fixture; see the frozen
[receipt](../../../reports/ref-005d-codec-checks-04.xml).
The final probe completion SHA-256 is
`d9b53c336cf078be6f242a6c543eaa87460c32d741dcee4bd3dbedbc3fd8867c`.

```bash
.venv/bin/python -B -m pytest -q validation/betse/native_recording/test_recording.py \
  --junitxml=reports/ref-005d-codec-checks-04.xml

.venv/bin/python -B validation/betse/native_recording/codec_job.py launch \
  runs/ref-005d-offline-codec-2026-09-17/qualification-01 \
  --tests reports/ref-005d-codec-checks-04.xml \
  --probe runs/ref-005d-codec-probe-2026-09-17/probe-02
```

The output must be fresh. Preserve frozen test receipts; a later deliberate
rerun requires a new receipt path and, after registration, a new source context.
Progress is in durable per-row reports/logs; `completion.json` or `failure.json`
is terminal. Launch detaches once and never polls, retries or launches a review.

After user-requested status and separate review: register the live same-1 ms
observer-parity replay and qualify the actual seven-cell Cells window/restart
path. Only then scope the independent reference/resources for 10 ms. Relaxation,
recovery, original-data biology and GPU/organ scaling retain their separate gates.
