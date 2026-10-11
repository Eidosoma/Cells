# REF-005d R0: output ownership correction and shared-worker qualification

2026-09-17, D128. The user authorized fixing the output collision, adding an
end-to-end worker regression and proceeding with the qualification. Preserve
the frozen D125/D127 implementations and all prior attempts. This is a separate
validation adapter, not a production change or an in-place evidence retry.

## Preserved failure

`runs/ref-005d-live-continuation-2026-09-17/continuation-01` stopped after
**79.799 s**. Native reuse had authenticated. The all-blocked 12.5 µs compiled
case completed baseline overlap and all three windows. The next, 25 µs case
encountered a harness path collision before disk-policy/restart qualification:
both the ordinary baseline and `full` window policy targeted `<case>/full`.
The production writer's non-overwrite guard correctly stopped the job.

- Registration: `0c06e8390acf07e0fbea47ebd2dd9a5d9dfbb63986f6534838d38fdcc735604b`.
- Failure: `7cd3c3d8cc4aa18b0ea6740adaf020b333fbc5619ff7c40d877bdd6c2e3ea070`.
- Cells failure: `9e94cc43a83ca03eb90345afc23d28bdcdc20eef26c135db6d42b4d55ee0bb40`.
- Saved packet: **24 files / 3,052,082 bytes**. No completion or accepted full
  Cells matrix exists. No partial Cells result is reused by this amendment.

The earlier real-Cells smoke called individual APIs in a different arrangement:
it did not write the ordinary baseline into the campaign's combined output
tree. New regression work must use the same worker and output planner as the
full campaign, not reconstruct an independently passing approximation of it.

## Correction and validation contract

The [new adapter](../validation/betse/live_recording_paths/README.md) separates
`baseline/`, `recordings/{full,observations,checkpoints}/` and `resumed/`. Require
fresh, non-overlapping paths before computing any case; keep all non-overwrite
protections. Verify the baseline's file hashes after recording/restart work.
Record the output layout in each case report and the registration.

Reuse the frozen numerical checkers and public Cells APIs. Preserve all
state/readout/layout/clock comparisons, diagnostic maxima, loaded checkpoint
semantics, restart suffixes, zero-length and sparse-readout cases. A source-level
test checks numerical branches against the original, normalizing only output
path expressions. Fast filesystem/orchestration tests use clearly labelled
stubbed physics; do not count them as numerical agreement.

One fresh detached job is preregistered with two sequential phases:

| Phase | Required work | Deadline |
| --- | --- | --- |
| Actual-worker probe | One real pump+leak, 25 µs compiled, 1 ms case: baseline, three windows, all three disk policies, loaded full and windowed restart, zero-length continuation | 120 s |
| Full matrix, only after probe passes | Same 24 baselines, 72 windows, eighteen disk outputs, six full and six windowed restart suffixes, six zero-length and two sparse controls | 750 s |

Both phases invoke exactly the same worker. Controller and matrix worker check
the probe's registration binding, result hash, complete file inventory, coverage,
failure absence and empty stderr. A failed or changed probe blocks the matrix.
The probe is one additional software/integration case; it neither substitutes
for a matrix case nor expands the scientific duration. Full matrix cases run
afresh under the corrected layout. Both phases use separate pinned CPU/JAX
float64 processes; no native worker or independent reference is invoked.

The source context incorporates the prior 674 inputs unchanged and the new
adapter/tests/contract. Authenticate all 24 stopped continuation files and all
964 native packet files, 36 capture/comparison/stream/index/chunk hash chains,
earlier passing source-bound software and the closed prerequisite chain. Bind
that inventory in the new registration; verify it before/after execution.
Native producer comparisons are carried forward, not independently re-audited.

## Commands and resource ownership

```bash
taskset -c 0-3 .venv/bin/python -B validation/betse/live_recording_paths/output_job.py check \
  runs/ref-005d-output-layout-2026-09-17/software-02 \
  --tests reports/ref-005d-output-layout-checks-02.xml

.venv/bin/python -B validation/betse/live_recording_paths/output_job.py launch \
  runs/ref-005d-output-layout-2026-09-17/qualification-01 \
  --checked runs/ref-005d-output-layout-2026-09-17/software-02/completion.json
```

The first fast suite retains **50 passes / one test-fixture failure**: the
baseline-corruption test used the pytest case directory itself as a phase,
causing the job-wide quota walk to encounter pytest's sibling symlink aliases.
Use a phase subdirectory, as the real controller does; do not relax the symlink
guard. Preserve `software-01` and its receipt. No actual model was run there.

All destinations/receipts must be fresh. Before/after source identity binds the
fast software result. Launch authenticates it, freezes the source capsule and
passes the registration hash to the controller and each phase worker.

Keep CPUs 0–3 / one BLAS thread, **1,800 s total / 16 GiB worker address space /
32 MiB per file / 512 MiB job-wide artifacts / 1 GiB free-disk reserve**; reserve
64 MiB before each case. The full-matrix deadline stays 750 s; the explicit new
probe adds a 120-second sub-bound within the unchanged overall limit. These are
safety caps, not runtime forecasts. Quotas include both phases and logs.

Detach once and return control. No polling, retries, automatic audits or later
campaigns. Failures and partial outputs remain durable. Success stays
`live_recording_and_matched_windows_pass_pending_independent_review`; no
production, scientific-threshold, native-history-retention, biological, GPU,
longer-horizon or full-BETSE-parity claim. Record evolving outcomes in
[Progress](../PROGRESS.md), outside this frozen source context.
