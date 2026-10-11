# CORE-010 v2 closeout handoff

2026-09-11. The user authorized the remaining closeout followed by a bounded
BETSE comparison. This is operational follow-through on D063, not another
simulation attempt or a change to the acceptance protocol.

**Completed successfully**, September 11 at 22:31 UTC; result inspected September
12 before further work. The [saved job result](../runs/core-010-2026-09-11/closeout-01/verification.json)
passes in 2154.841 seconds: audit 381.956 s, six-context regression 1771.086 s,
closeout 1.608 s. All **4190 tests pass**, with no failures, errors or skips.
The [development closeout](core-010-v2-closeout.json) passes without stable promotion.

## Completed capture

The [acceptance-02 result](../runs/core-010-2026-09-11/acceptance-02/verification.json)
has status `pass`: 4381.787 seconds (73 minutes), 57 scalar runs, 12 streams,
53 comparisons and 912 payload files. All fourteen eager trajectories completed.
Its 352 captured implementation/protocol files and all 51 production modules
must remain unchanged. The stopped v1 attempt remains preserved and unaccepted.

## Detached, fail-fast closeout

Launched at `2026-09-11T21:55:32.939659+00:00`, PID `1734359`, in its own OS
session. The [launch receipt](../runs/core-010-2026-09-11/closeout-01/launch.json)
records dispatch, not completion. No repeated automatic assistant polling was performed.

The job uses the existing unmodified auditor, regression driver and closeout:

| Stage | Limit | Result artifact, once completed |
| --- | --- | --- |
| Separate saved-data/physical audit | 1800 s | `reports/core-010-v2-full-audit.json` |
| Six-context regression matrix | 3600 s | `reports/core-010-regression-03/verification.json` |
| Development acceptance closeout | 300 s | `reports/core-010-v2-closeout.json` |

These limits belong to the follow-up job, not the already completed capture.
Children use CPU 0–3, single-thread BLAS/OpenMP and CPU JAX. Each stage has a
separate timeout with a 15-second termination grace. A nonzero exit, timeout,
changed captured source or failed result stops the chain and retains all outputs.
There is no automatic retry, stable-version promotion, BETSE execution or
additional simulation capture. Regression tests may execute their normal checks.

The operational wrapper lives in the run directory, outside the frozen
implementation set. It invokes the existing checks without changing their
equations, source checks, coverage, tolerances or result handling. New documentation
does not alter the captured implementation; no new comparator code enters the
source set before closeout.

Job directory: [closeout-01](../runs/core-010-2026-09-11/closeout-01).
`launch.json` records the process, commands, budgets and source identities.
Each stage has separate stdout/stderr logs and start/completion receipts.
`verification.json` means the full job passed; `failure.json` records a failure.
The directory and outputs are non-overwriting. Do not infer completion from a
start receipt or a passing earlier stage.

The job finished detached. Status was checked at the user's request; it is no
longer running. Bounded development acceptance is complete at **0.15.0.dev0**;
stable production remains **0.14.0**.

Its source/evidence identity was [authenticated before edits](ref-003a-preservation.json).
The subsequently authorized [REF-003a passive-law contact](REF003A_PASSIVE_CONTACT.md)
now passes separately. No BETSE trajectory or biological validation follows from
this internal closeout. REF-003b model alignment is next, with no long job scheduled.
