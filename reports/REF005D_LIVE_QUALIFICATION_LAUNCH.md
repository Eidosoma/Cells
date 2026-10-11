# REF-005d R0: preflight closeout and full live/window qualification

2026-09-17, D126. The user has authorized proceeding after the detached D125
software/smoke preflight passed. Launch the already implemented, frozen D125
campaign without changing its code, numerical scope or resource limits. D126
records execution authorization and preflight closeout; it does not relabel the
frozen controller's `D125` registration or its earlier handoff.

## Completed preflight

The [preflight completion](../runs/ref-005d-live-preflight-2026-09-17/detached-01/completion.json)
reports `live_window_software_preflight_pass`, finished **2026-09-17
14:36:43.757 UTC**. All **79 tests pass in 54.27 s**; the complete source-bound
job took **77.511 s**, including prerequisite/integrity checks. Both actual
native smoke modes exactly match their accepted records. The real Cells smoke
passes accepted-baseline overlap, windowed execution, all three disk recording
policies, a loaded complete-checkpoint restart, zero-length continuation and
sparse-observation checks.

Before the full launch, verify all **235 sealed payloads / 239 regular files /
26 explicitly recorded internal pytest aliases**, **668 frozen source/helper/
contract inputs**, their complete source capsule and the passing XML receipt.
The current campaign's source manifest is exactly the same as the tested one.
The completed preflight retained **5,571,167 bytes before completion**; this is
preflight evidence storage, not a full-campaign projection or memory estimate.
The root/controller and test-runner stderr files are empty. Earlier adapter
failures, setup errors and the 45-second smoke timeout remain preserved.

Evidence identities:

- Preflight registration:
  `1bc4ac469027156de3d84cbf1bd03cc7b259e9b44ab449795e5f894b467a5431`.
- Preflight completion:
  `b0ba23dc666ef5a4a328bb9be0f55bd009bb86cf14eb2893a7d2d790e168a224`.
- [Passing 79-test receipt](ref-005d-live-checks-03.xml):
  `b787b9962a4b0d96e327ab0c57e0e10bfe52ab8e47488ceabb080a71abc5aa20`.
- Canonical source-manifest SHA-256 (sorted compact JSON, UTF-8):
  `af9d302b5bdc3f667a7ebbe7ad0c4439a3025fddf17c74205e83b924cdbe778c`.

These are saved-evidence checks, not another simulator, test-suite or independent
physical-law audit run. The preflight did not launch this campaign automatically.

## Full qualification scope

Use the existing [live/window contract](../validation/betse/live_recording/README.md)
and [frozen D125 handoff](REF005D_LIVE_HANDOFF.md). Their statements that the
full campaign was not yet launched are historical. The source context stays
unchanged so the passing preflight applies to precisely the code being run.

The seven-cell pump–leak preparation remains **1 ms** with unchanged geometry,
chemistry, native/Cells timesteps, physical equations and scientific thresholds.

| Work | Required coverage |
| --- | --- |
| Native live streams | Six controls × three grids × full-observer/storage-only modes: 36 runs, all exactly compared with accepted records |
| Native neutrality | Eighteen new pairs; 6,720 observed updates and 13,404 history samples |
| Cells ordinary runs | 24 full trajectories, each exactly compared with its accepted saved trajectory |
| Cells window paths | 72 comparisons at widths 1, 7 and 64, including all state/readout/layout/clock fields and diagnostic maxima |
| Cells disk policies | Eighteen full/observations/checkpoints outputs, all payload/index/checkpoint hashes checked |
| Cells continuation | Six loaded full and six windowed restart suffixes, six zero-length continuations and two sparse-observation controls |

The storage-only native mode still uses a recording hook; it is checked against
the accepted truly quiet baseline as well as the new full-observer partner.
Native histories, time schedules and pickle creation remain intact. This is
**not a constant-memory BETSE claim**. Keep numeric history payloads, encoded
buffer sizes and whole-process RSS distinct. Native pickles are retained and
hashed, not loaded or qualified as native restarts.

## Execution and limits

```bash
.venv/bin/python -B validation/betse/live_recording/live_job.py launch \
  runs/ref-005d-live-recording-2026-09-17/qualification-01 \
  --tests reports/ref-005d-live-checks-03.xml
```

The destination must be new. The controller authenticates the closed prerequisite
chain, captures the same **668 inputs**, passes its registration SHA to both
workers and rechecks sources and evidence after execution. Native and Cells use
their separate pinned interpreters. The final result also checks exactly 72
known disabled-cut notices in native stderr; these are not described as an
absence of all notices.

Unchanged limits: **CPUs 0–3 / one BLAS thread / 1,800 s total / 900 s native /
750 s Cells / 32 MiB per file / 512 MiB aggregate / 1 GiB free-disk reserve**.
Worker address-space caps are **8 GiB native / 16 GiB Cells**, not RSS targets.
The native sink separately permits 32 records / 8 MiB encoded bytes per chunk
and 32 MiB per stream. Reserve 64 MiB before each new row/case. The 30-minute
overall cap is a safety limit, not a measured runtime or ETA.

Launch detached once and return control to the user. Durable per-row artifacts,
phase logs and `completion.json` or `failure.json` record the outcome. No polling,
automatic retry, independent follow-up audit, broader regression, longer-horizon
experiment or GPU job is part of this launch.

Success would be `live_recording_and_matched_windows_pass_pending_independent_review`.
A launch acknowledgment is not that success. Full R0 independent closure, 10 ms
reference/domain scoping, biological validation and GPU/organ-scale execution
remain separate gates. Current launch identity is recorded in
[Progress](../PROGRESS.md), outside the frozen source context.

## Launch acknowledgment

Launched **2026-09-17 15:07:05.957 UTC**, PID **3466859**, at
`runs/ref-005d-live-recording-2026-09-17/qualification-01`.
Registration SHA-256:
`3eb0443fb6818e6fca6155315e74edbf3c0e16c2713bad6d5686853bca075665`.
The source/prerequisite checks and launcher returned successfully. No worker
status/completion poll or automatic follow-up was performed. This acknowledgment
does not claim a completed native phase, Cells phase or full acceptance.
