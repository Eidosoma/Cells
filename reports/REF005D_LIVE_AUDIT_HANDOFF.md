# REF-005d R0: independent live-output review contract

2026-09-17, D129. The user authorized the next review after D128 completed.
This document and the independent reviewer are frozen into its source capsule.
Launch/status updates belong in a separate report, not this frozen contract.

## Inputs and boundary

D128 registration:
`1cd7694949963f6f8d80bb222b78c5a039eb4a8425c1d20b5674dd35d72d8b33`.
D128 completion:
`bb6448d1be688c1b3613e8580c3e365cc75a6a794fb6bab22f7fffa4612bf2c1`.

The qualification completed in **553.910 s**, including the separate **36.037 s**
actual shared-worker probe and **500.927 s** matrix. Its producer verdict is
passing **pending independent review**. Authenticate 516 sealed payloads / 520
regular files, 680 source inputs/capsule, source-bound 51-test software result,
54 probe and 450 matrix files, and all prerequisite evidence. Native data are
the 36 completed D126 runs; no new native or Cells run is authorized here.
D126 and D127 remain failed attempts; their entire 964/24-file packets stay intact.

## Independent checks

1. Decode each live stream with the qualified D124 reader and compare directly
   with the accepted original D119 JSON: every type/value, exact binary64 bits,
   signed zero, complete history/endpoint digests and full record exhaustion.
   Then check all 18 observed/quiet pairs over their common fields.
2. Independently decode saved Cells arrays using the qualified standard-library
   NPY reader, without importing Cells, NumPy/JAX, BETSE or producer modules.
   Check exact baseline overlap, saved restart suffixes, complete checkpoint
   state/layout, global clocks/cursors, config/runtime/source seals and file sets.
3. Check disk policies and window indexes against the accepted full baseline:
   step order, boundary observations, deduplicated accepted samples, sparse chunks,
   requested midpoint and initial/final snapshots. Reject missing/extra payloads.
4. Reconstruct expected comparison-receipt digests for in-memory window outputs
   that were **not saved**. Cover 72 matrix windows, six restart windows, six
   zero-length cases, two sparse controls, and the separate probe's three windows,
   restart window and zero-length case. Do not describe these as direct comparisons
   of persisted window arrays. Their assurance remains tied to the sealed producer
   comparison receipts and software tests.
5. Link complete-window diagnostic maxima to accepted saved summaries and disk
   index reductions; restart maxima to the persisted suffix summary. Zero-length
   maxima are only checked for schema, finiteness and baseline bounds. No fresh
   physical-law evaluation or biological validation is performed.

Matrix direct evidence: 24 baselines, 18 disk recordings, six saved restart
suffixes; probe adds one baseline, three recordings and one suffix. The original
1 ms scientific validation/tolerances remain unchanged. Estimated working-byte
reservations are bounded reported estimates, not independent peak-memory measurements.

## Software gate and operation

A source-bound passing short suite is mandatory before launch. Exercise saved
checkpoint-heavy and sparse cases, an actual native row/pair, handwritten array
bit fixtures, resealed checkpoint/index/payload corruption, receipt corruption,
unsafe paths, import fence, prerequisite authentication, coverage refusal and
detached failure handling. Failed software attempts retain their logs/artifacts.

Launch one detached review: CPUs 0–3, one BLAS thread, 900 s deadline, 4 GiB
address-space cap, 8 MiB per new file, 64 MiB new artifacts, 1 GiB free reserve.
Before and after review, authenticate frozen source and prerequisite inventories.
Write per-row/per-case reports, durable logs and a terminal completion or failure.
Return control after launch; no polling, automatic retry or follow-up work.

Only the complete review may mark saved live outputs and expected receipts
independently closed. This does not qualify a longer horizon, whole-native
bounded memory, dynamic metabolism, biological realism beyond the existing
fixture, or GPU execution. No production, solver, physics or tolerance edits.
