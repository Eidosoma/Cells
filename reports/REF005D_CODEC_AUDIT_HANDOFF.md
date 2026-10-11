# REF-005d R0: independent offline codec review handoff

2026-09-17, D124. Launch one detached, read-only review of the completed lossless
conversion; do not rerun a simulator or automatically start a live replay.

## Captured result and immutable inputs

D123 finished **2026-09-17 12:27:44.797 UTC / 215.987 s** with all 36 canonical
row round-trips passing. Its six-control matrix contains 6,720 observed updates,
13,404 history samples and 20,196 stream records. Storage fell from
**1,509,951,698 to 18,070,684 bytes**, a factor of 83.558. Largest compressed
stream file: 45,886 bytes; peak encoded chunk: 1,088,005 bytes. The reported
548.68 MiB converter high-water RSS includes legacy/decoded full trees and is
not a live-memory bound.

Capture: `runs/ref-005d-offline-codec-2026-09-17/qualification-01`.
Registration SHA-256:
`092cd7db7dc3dd9d7d1378607a67ecf16687b249bdded1765eaeceef75529847`.
Completion SHA-256:
`9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379`.

Authenticate all 778 sealed payloads, fourteen captured source/helper/contract
files, source capsule, software/resource receipts and the original accepted
pilot/rejected-attempt chain. Freeze the four operational files as well when
registering this review. Preserve all old archives, source bytes, physics and
scientific tolerances. The 55 production modules remain unchanged.

## Independent method and preflight

Use the [new read-only review implementation](../validation/betse/native_recording_audit/README.md).
The producer codec, partitioner, row reconstruction and job modules are forbidden
imports, as are Cells, BETSE, NumPy, SciPy and JAX. Shared helpers authenticate
prior evidence only; no numerical solver or physical-law re-evaluation occurs.

Decode all chunks independently. Compare every nested original value directly,
with exact type and float64-bit equality including negative zero. Independently
verify complete original-field coverage and primitive counts, ordered records,
history/final array byte digests, clock/raw-call/lifecycle preservation and
actual storage/encoded-buffer metrics. Do not trust a producer canonical digest
as a substitute for decoding and comparison. A partially consumed stream cannot
close a row.

Preflight tests cover manually encoded wire cases, corruption even with renewed
outer hashes, incomplete/misordered traces, type/signed-zero changes, omitted or
extra fields, bounded reader release with cyclic GC disabled, all six actual
coarse-grid controls in both modes and a complete actual finest 640-update
pump+leak row. Source/import guards and detached failure behavior are separate
checks. The final passing software receipt is bound by the review registration.

**133 preflight checks pass / 52.34 s**. Receipt:
`reports/ref-005d-codec-audit-checks-02.xml`, SHA-256
`808895f7f6df01981312241077e75f1c568595496c2b4ff6e6c2591e2ac2d8fd`.
The actual coarse controls and complete finest pump+leak row pass the separate
decoder, direct-value coverage and independent array-digest checks. Those
preflights do not replace review of the full 36-row packet.

## Registered execution and handoff

Target: `runs/ref-005d-codec-audit-2026-09-17/audit-01`.
Caps: CPUs 0–3, 600 seconds, 4 GiB address space, 4 MiB per output file,
32 MiB review artifacts and a 1 GiB free-space reserve. The original input row
is materialized; the new decoder retains only bounded chunks/values. Measure
reviewer RSS without reclassifying it as live simulator memory.

Freeze review sources, tests, handoff and the exact completed codec inventory.
Pass the registration digest explicitly to the detached worker. Retain per-row
reports and stdout/stderr, and publish either a complete final manifest or a
durable failure. No polling, automatic retry, audit, regression or follow-up.

Passing status would be `offline_lossless_recording_independently_closed`.
This closes only the offline codec sub-gate. After user-requested status and
review closeout, separately prepare live same-1 ms recording neutrality and
the actual seven-cell Cells window/restart checks. Neither R0 as a whole nor
10 ms, native restart, biological validity, release promotion or GPU is closed
by this job.
