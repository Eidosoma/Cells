# CORE-010 recorded development acceptance

2026-09-11. The passive spatial production equations remain **0.15.0.dev0**,
byte-identical to the completed development integration. **0.14.0 remains the
accepted stable release.** This page tracks the next engineering gate, not new
physiology, biological plausibility or GPU performance.

## Status

The prospective [acceptance protocol](../docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE.md)
is frozen in [acceptance-01](../runs/core-010-2026-09-11/acceptance-01/registration.json).
Its registration captures 346 source/protocol files and 42 full scalar definitions
before execution. **The session stopped at its 3600-second wall budget during
eager validation and is not accepted.** The [failure](../runs/core-010-2026-09-11/acceptance-01/failure.json)
records `TimeoutError`; cleanup completed at 3600.779 seconds. No automatic
retry, tolerance change, production edit or stable-version promotion followed.

The [stopped-evidence receipt](core-010-stopped-preservation.json) authenticates
all **880 files / 77,070,916 bytes**, the original implementation capsule and
unchanged source/runtime/protocol identities. All session children have exited.
Ten eager cases completed; `divalent`, `line_32` and `pure_bulk` were interrupted,
and `line_8` had not started. These four do not count as passing full eager runs.

| Recorded path | Completed | Status |
| --- | --- | --- |
| Compiled selected-step trajectories | 14/14 | Independent saved-data audit passes |
| Compiled smaller-step trajectories | 14/14 | Independent saved-data audit passes |
| Fresh-process scalar restarts | 14/14 | Independent audit and strict byte replay pass |
| Future-control branch | 1/1 | Recorded; independent state/readout/cubic audit passes |
| Full eager trajectories | 10/14 | All ten completed cases independently audit; four remain unqualified |
| Scalar windows | 4/4 | Independent artifact/physics audit passes |
| Original/resumed independent-world cohorts | 8/8 | Independent artifact/physics audit passes |

The [non-eager subset audit](core-010-non-eager-audit.json) passes all 43 scalar
and 12 stream runs without trajectory integration. It checks complete native
and observed state, all 26 physical readouts, whole-Hermite bounds and checkpoint
identity. Its first console result was truncated by the tool; the retained
[truncated log](core-010-non-eager-audit-truncated.log) is not a complete receipt.
A compact read-only repeat supplies the complete JSON receipt above; no ODE was
rerun. A separate [byte audit](core-010-restart-byte-audit.json) confirms all
1,022 scalar-restart arrays, including signed zeros, dtypes and shapes.

The [first eager subset](core-010-eager-subset-audit-01.json) and
[remaining completed subset](core-010-eager-subset-audit-02.json) pass all ten
completed cases against independent equations/reference and the stricter
compiled/eager comparison. All [25 cross-path comparisons](core-010-cross-path-audit.json)
pass; the future-control branch retains nonzero history and all 73 arrays match
its full-run suffix byte-for-byte. The [checkpoint inventory audit](core-010-checkpoint-inventory-audit.json)
loads all 166 scalar and 24 cohort checkpoints and checks unique numeric members.
The complete [regression matrix](core-010-regression-02/verification.json) passes
all **4084 tests**, with no failures, errors or skips. Its 345 implementation
files match the registered capture exactly; the additional frozen protocol file
also remains unchanged. This regression result does not replace full acceptance.

| Test source context | Passing tests |
| --- | ---: |
| Current 0.15.0.dev0 | 2334 |
| Preserved 0.10.0 | 971 |
| Preserved 0.11.0 | 205 |
| Preserved 0.12.0 | 213 |
| Preserved 0.13.0 | 256 |
| Preserved 0.14.0 | 105 |

The thirteen prospective NUM-009 v1 complete-session tests remain explicitly
unexecuted, not counted as passes: that older session stopped without complete
evidence. Its maintained v2 replacement and stopped-evidence tests are included.

The preserved NUM-010 audit again verifies 339 payloads, 21 sources and fourteen
restarts without importing production or running an ODE solver. All 235 old
scalar/21 cohort checkpoints load under archived 0.14.0, with exact archived
replay and current-source migration refusal. Earlier-family replay passes 78
scalar/window cases, ten independent batches and 54 later-family trajectories.

The original full-panel auditor/release closeout has not passed: there is no
`verification.json` in the stopped session. Passing subsets are not a substitute
for the missing full eager coverage and registered session verdict.

All **122 new preflight tests pass** in 90.39 seconds with warnings treated as
errors ([combined receipt](core-010-acceptance-preflight-04.xml)). There are 102
scalar/reference/readout/corruption tests and 20 stream/cohort/structure tests.
The new audit also passes on the prior full one-cell development recording.

The first preflight retains three failures and 99 passes. Two were new auditor
mistakes: the reference's capacitance-component order is not public outside-owner
order, and an almost-zero net current requires propagated species-flux error
rather than relative error on the cancelled sum. The third incorrectly poisoned
production RHS during the normal checkpoint loader's required domain preflight;
the independent oracle is now tested separately with RHS/observer poisoned.
No production code or inherited scientific tolerance changed. Corrected scalar
preflight 02 passes all 102; stream preflight 03 passes all 20.

## Scope and preservation

The [pre-work baseline](core-010-acceptance-workspace-baseline.json) authenticates
707 existing worktree files, including the preceding closeout and 3962-test matrix.
All 707 still matched immediately before formal capture; all 51 production modules
and version are unchanged. At closeout, **703 of 707 pre-existing files remain
byte-identical**; only README, PROGRESS, the spatial guide and decision log have
expected status updates, with none missing. New code only concerns prospective
run orchestration, saved-data audits, corruption tests and acceptance closeout.
Lint passes and all 282 Python files pass formatting checks.

The separate [tooling/preservation closeout](core-010-audit-tooling-closeout.json)
binds the regression logs and JUnit counts, frozen implementation capsule,
completed-subset audit receipts, unchanged stopped payloads and preserved accepted
source/evidence. Its passing status applies only to that scope; it explicitly
records `formal_acceptance_status: stopped_not_accepted` and no release promotion.

The panel requires all fourteen full compiled/eager/refined/restarted cases, a
nonzero-history future branch, four scalar window runs and four original plus
four fresh-process resumed cohorts. Every recorded state and all 26 physical
readouts are independently checked, with complete checkpoint and chunk identity.
Earlier accepted model arrays must replay exactly, and old checkpoints are loaded
only under their preserved source context.

The session was capped at 3600 seconds and 2 GiB, using CPU 0–3 and four one-CPU
eager lanes. The completed initial 0.3-second eager cases took roughly 30 minutes
on their assigned lanes. This is uncompiled JAX validation cost under this run's
CPU conditions, not compiled simulator throughput or a GPU benchmark. The
prospective one-hour whole-panel budget was insufficient.

Next: document a separate, realistically budgeted acceptance attempt, then run
and independently audit the complete panel. Do not edit this frozen v1
protocol retrospectively, drop slow cases, weaken scientific tolerances or label
the stopped session accepted. Stable version promotion remains a subsequent
source-preservation/replay closeout. The prepared `close_core010_acceptance.py`
requires a passing full session and must not be used to close this stopped run.
