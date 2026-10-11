# REF-005d R0: offline lossless-recording handoff

2026-09-17, D123. One detached **saved-data codec qualification**, not a new
simulation, physical-law audit or longer-duration acceptance run.

## Evidence and scope

Prerequisite: the [independently closed refined 1 ms pilot](REF005C_PUMP_PILOT_CLOSEOUT.md).
Its capture completion SHA-256 is
`45bc4adf9986bf4adc9750af969818b1cf4e0466854e01dbf136e02eb23cba6f`;
independent closure is
`e2e67df2b6118cdacfcbf4f23357a972bcb6ecae7d4eacad3f02956ab4369bc1`.
Authenticate all prior inputs/payloads before and after conversion. The old
six-miss attempt, all accepted archives and all 55 production modules remain
unchanged. No frozen observer/producer is edited.

Convert all 36 saved native records at 6.25/3.125/1.5625 µs, both observed and
unobserved for six controls. Require exact canonical reconstruction of every
original row, with signed zero and numeric types preserved. This covers 6,720
observed updates, 13,404 history samples, every raw call and physical boundary,
and all endpoint/lifecycle metadata. Resulting stream count: 20,196, including
72 initial/terminal records. No physical tolerance is introduced or changed.

Implementation and binary/layout contract: [native_recording](../validation/betse/native_recording/README.md).
Static metadata starts each stream; histories follow actual update order;
endpoint arrays and terminal hashes close it. The header needs no future state.
The generic bounded sink is reusable; the pump adapter is explicitly versioned
and refuses unknown fields. No simulator, producer, NumPy, SciPy or JAX imports.

## Preflight and resource contract

**132 software checks pass / 3.51 s**. The final test receipt is
`reports/ref-005d-codec-checks-04.xml`, SHA-256
`d7d124a2f6a5e39528af20b2796fd7e1932d226eee734b5a71fa7365c5e34d2a`.
Coverage includes
all twelve real short rows, scalar types/bytes, signed zero, corrupt/truncated
streams, malformed call/order/history evidence, missing footer, quotas,
source binding, import fencing, detached dispatch and durable failures.
The writer/reader allocation check uses 2,500 generated records with cyclic GC
disabled; buffer release must not depend on garbage-collection scheduling.

The source-bound final largest-row probe is
`runs/ref-005d-codec-probe-2026-09-17/probe-02`. Its predecessor is preserved;
only the final implementation's matching receipt can authorize this launch.
Its completion SHA-256 is
`d9b53c336cf078be6f242a6c543eaa87460c32d741dcee4bd3dbedbc3fd8867c`.
The **143,185,735-byte** legacy row reconstructs exactly from **1,549,225 bytes**:
92.424× smaller. Peak encoded chunk: 1,087,999 bytes; largest compressed file:
38,726 bytes. Full offline conversion/check: 38.519 s; high-water process RSS:
504.82 MiB, including legacy JSON and the complete decoded tree.
Actual probe measurements and
hashes are bound by registration; do not transfer its memory result to a live
observer or its compression factor to every case without the full matrix.

Registered caps: CPUs 0–3; 900 s total; 4 GiB address space; 16 MiB/file;
32 MiB per stream; 512 MiB aggregate; 1 GiB free-disk reserve. Encoded chunks
are at most 32 records / 8 MiB, not 8 MiB whole-process memory. Current/high-water
RSS and buffer lengths are reported separately. The offline importer and
compatibility decoder deliberately materialize whole rows for exact checking.

The launcher freezes source/helper/contract files, software and probe receipts,
all 36 old input identities, and a source capsule. The worker receives the
registration digest as an argument so it cannot silently accept a changed
registration. Per-row completion reports/logs survive partial failure. Publish
successful terminal status only after all rows, quotas and source checks pass.

## Handoff behavior

Target: `runs/ref-005d-offline-codec-2026-09-17/qualification-01`.
Success would mean `offline_codec_exact_pending_independent_review`, **not**
R0 closure, live observer neutrality, bounded BETSE memory, 10 ms qualification,
biological plausibility, release promotion or GPU readiness.

Launch once detached and return to the user. No polling, automatic retries,
follow-up audit or regression. After user-requested status, review the evidence
and proceed separately to live recorder parity and the matched Cells window/
restart checks. Do not reset accounting histories, hide numerical failures or
make Cells reproduce upstream errors to accelerate a later benchmark.
