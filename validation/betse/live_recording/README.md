# Live native recording and matched Cells windows

2026-09-17, D125 / REF-005d R0. New validation-side adapter; **no production,
upstream physics, timestep, duration or scientific tolerance change**. The
[offline codec is independently closed](../../../reports/REF005D_CODEC_CLOSEOUT.md).
Its producer and independent reviewer are frozen and reused without edits.

**Current execution is the detached 79-test software/smoke preflight, not the
full matrix below.** The expanded Cells smoke reached its initial 45-second
time cap (75 other checks pass). Preserve that incomplete attempt; the new
preflight allows 120 seconds for that smoke and 300 seconds overall. The full
campaign waits for a passing source-bound receipt and another user instruction.

## Ownership and lifecycle

`live_observer.py` uses the same source/instance-scoped profiling boundaries as
the closed pump observer, but retains only one pending physical update and raw
call group. Records go immediately to the existing 32-record / 8 MiB encoded
chunk sink. There are no accumulating observer `steps`, `raw_steps`, labels,
sampled-index or storage lists. Native method wrappers are respected; only
direct toolbox calls count as pump/passive membrane calls. Exception unwinds
are not successful returns. Missing/duplicate boundaries, raw-call returns,
history writes, lifecycle closure and terminal array checks fail closed.

BETSE parameter float subclasses are copied into plain JSON scalar types using
the legacy serialization semantics. No decimal rounding, numeric tolerance,
native-object mutation or codec relaxation is involved. Signed zero, numeric
types and float64 bits are checked. The header records source-backed metadata
and expected array extents at actual loop entry. Each subsequent history sample
is copied after the original `write2storage` returns. All history byte hashes
are checked again against native retained histories at completion, without
constructing a full JSON history.

**BETSE's own histories, time-step array/set, storage calls and pickle creation
remain unchanged.** Streamed observation does not make the native simulator
constant-memory. Record numeric payload bytes for all native history lists,
process current/high-water RSS and encoded chunk/record sizes separately. The
full memory footprint includes Python containers, library state and native
arrays; numeric payload bytes are not a process-memory estimate.

The schema retains the historical `unobserved` mode label, but the new adapter
in that mode still has a **storage-only observer**. It does not take the full
physical trace. It must match the independently accepted original truly quiet
row exactly, and all shared fields must match the new full-observer partner.
This is an explicit three-way neutrality comparison, not an assertion that the
storage-only run has no hook. No new native restart claim is made; pickle files
are retained and hashed, never loaded.

## Registered matrix

- Native: same six controls, 6.25 / 3.125 / 1.5625 microsecond steps, same 1 ms
  horizon, full-observer/storage-only pairs: **36 rows / 18 pairs / 6,720 observed
  updates / 13,404 history samples**. Compare every stream record against D123's
  independently decoded exact counterpart, including metadata and terminal data.
  A separate comparison checks all shared fields of each new pair.
- Cells: ordinary checked RK4 APIs, same **24 full trajectories** (three compiled
  steps and one eager step per control), each exactly compared with its saved
  accepted trajectory. Run **72 window comparisons**, widths **1 / 7 / 64**,
  including all state fields, readouts, layouts, step/event indices and diagnostic
  maxima. Checkpoints do not reset cumulative transfer/energy ledgers.
- Actual disk policies: **18 outputs**, six controls × full / observations /
  checkpoints at 25 microseconds, width 7. Verify index coverage, hashes, saved
  fields and identical diagnostic maxima even when no trajectory is recorded.
  Load each complete 0.5 ms snapshot from checkpoints-only output and compare
  six full and six width-3 restarted suffixes. Also check six zero-length
  continuations and two sparse-observation-schedule controls.

The Cells comparison sink sees fully checked, read-only windows and releases
each window. Full baseline trajectories are intentionally held for this bounded
qualification; the harness is not a constant-memory production workload or a
benchmark. Production already supplies windowing/recording/restart; this adapter
does not replace a solver to achieve test agreement. Reuse the public APIs.

## Files and failure behavior

- `live_context.py`: identities, full prerequisite authentication, source capsule,
  CPU environment, quotas and memory measurements.
- `live_observer.py`, `live_native.py`: new native observer/driver.
- `stream_compare.py`: incremental exact comparison using the independently
  qualified decoder, not a rebuilt whole trajectory.
- `matched_windows.py`: full/window/recording/checkpoint checks on public Cells APIs.
- `live_job.py`: fresh source-bound registration, detached controller, separate
  native and Cells interpreters, durable per-row reports and terminal result.
- `preflight_job.py`: separately bounded detached software/smoke run; produces a
  test receipt but never starts `live_job.py` automatically. It owns the test
  process group, records internal pytest aliases and preserves failures.
- `test_live_recording.py`: real saved-boundary replay, negative cases, GC-disabled
  release, direct real-native and real-Cells smokes, orchestration tests.

Caps: **CPUs 0–3, one BLAS thread, 1,800 s overall, 900 s native / 750 s Cells,
32 MiB per file, 512 MiB aggregate, 1 GiB free-disk reserve**. Native/Cells
workers have respectively **8 / 16 GiB address-space** limits, not RSS targets.
The native sink independently enforces 32 MiB per stream. Reserve 64 MiB before
each new row/case; preserve partial artifacts on failure. The overall cap is a
safety bound, not an ETA. A failed run is never retried automatically.

The controller binds its registration SHA at launch, authenticates all frozen
sources before/after workers, and rechecks the complete prerequisite chain
before/after execution. Long work detaches once; no completion polling, automatic
audit, regression campaign or longer-horizon run is launched. See the
[handoff](../../../reports/REF005D_LIVE_HANDOFF.md) for exact commands and receipts.

Success is `live_recording_and_matched_windows_pass_pending_independent_review`.
That is producer qualification, not independent R0 closure, whole-BETSE memory
qualification, biological validation, GPU performance or a 10 ms result.
