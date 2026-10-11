# REF-003e1: held-input response pilot handoff

2026-09-13, D081. **Implementation checks pass; response results are separate.**
This document is frozen before launch and does not report a completed simulation.
The [contract](../docs/BETSE_HELD_RESPONSE_PILOT.md) specifies the experiment.

## Implemented

Eight actual native SIM runs and 24 unchanged Cells runs are prescribed across
baseline, enabled zero amplitude, static block and suppression/recovery.
The setup is seven cells with a finite shared bath, matched F/R constants,
1 ms duration and one fixed 25 µs input hold. Native observer-off/on partners
test noninterference; Cells eager/JIT runs use subdivisions 1/2/4 of the same
held input. No production equation, runner, dependency or old adapter is edited.

New control-aware capture links event application to actual subsequent states
and fluxes. Saved-data arithmetic checks prescribed controls, interval-specific
permeability, inventories/charge, GHK rates and owned/shared-bath transfer.
Complete state histories and selected-boundary readouts are retained. State and
cumulative ledgers have 41 boundaries; matched fresh rates have 40 interval
starts. Per-interval transfers are compared separately. Cells' final held RHS
is checked internally; no fresh native final RHS is fabricated from stored current.

## Software evidence

All **122 focused tests pass in 21.41 s**, with warnings treated as errors and
no failures, errors or skipped tests in
[checks-03](ref-003e1-response-checks-03.xml). All **359 Python files** pass lint
and formatting checks. These tests read saved native/Cells evidence and use
explicitly synthetic corruption/prescribed-state fixtures; they do not integrate
either simulator. No old full suite or production acceptance matrix was rerun.

Coverage includes actual retained no-op state/flux records, actual D080 input
tables, exact observer/zero controls, timestep and observation sides, dynamic
diffusion, source nonce behavior, all export shapes/hashes, padding/disabled
routes, ownership and shared-bath ledgers, GHK/current/charge, final held input,
comparison failures, source/runtime/capsule provenance, timeouts, partial native
observer export and a launcher with no poll/wait method.

Earlier software receipts remain immutable:

- [checks-01](ref-003e1-response-checks-01.xml): 111 passed, three failed in
  20.65 s. The numerical checks passed; three test assertions overestimated
  their count. The corrected exact count is 14,826 per native observed row,
  derived from the declared checks, without changing physical tolerances.
- [checks-02](ref-003e1-response-checks-02.xml): 121 passed, one failed in
  18.36 s. A newly added synthetic pulse-readout fixture reused mutable rows
  across observation times; the held-control gate rejected it. Independent
  fixture rows fixed the test. No model, pulse law or criterion changed.

Before the final checks, execution validation also gained repeated accepted-
implementation/runtime and prelaunch input-hash checks. No actual response
attempt, retry or source change after capture preceded this freeze.

## Preservation and prospective resources

The [preservation record](ref-003e1-response-preservation.json) starts from
954 existing files. Only seven existing status documents may change. Preserve
D080's 201-file packet and 80-file capsule, the older evidence chain and all
352 accepted implementation files / 51 production modules. The new capture
adds eight adapter inputs (seven Python files and one JSON plan), making an
**88-file source capsule**. The installed **332-file BETSE Python package**
must still match the pinned upstream checkout.

The [prelaunch receipt](ref-003e1-response-prelaunch.json) binds source, plan,
test and preservation hashes before registration. Resource estimates come
from retained measurements, not the not-yet-run pilot: 134 s native, 1894 s
Cells and 120 s comparison, plus explicit total allowance; approximately
136,459,177 bytes of output. The slowest retained eager cost is approximately
1.036 s per accepted step; it is used for budgeting, not advertised throughput.

Hard stage caps are **180 / 2100 / 180 seconds**, under **2520 seconds total
(42 minutes)**. Use CPUs 0–3, single-thread numeric libraries, CPU float64 with
JIT available, **512 MiB artifacts** and **64 MiB per worker file**. File-size
limits are OS-enforced; overall bytes are checked between completed rows/stages
and at completion, not a filesystem quota or a peak-RAM measurement.

## Detached capture and interpretation

Fresh intended run directory:
`runs/ref-003e1-response-2026-09-13/capture-01`.

The exclusive registration and source capsule precede launch. The separate
`launch.json` records the actual PID/time; this handoff is not a launch receipt.
Stage logs, native/Cells completed records and failure artifacts stay in that
directory. A numerical rejection retains `comparison.json` plus `failure.json`
and never writes a passing capture receipt. Python-level native exceptions
also export partial observer state; hard timeouts preserve already written
files but cannot export unwritten state or imply resumability.

**A coarse native baseline discrepancy is expected to remain possible.**
Retained 25 µs native runs already missed shared-bath comparison criteria.
The unchanged criteria must count those failures, even if control, solver or
backend checks pass. Do not ignore them, widen thresholds, substitute a finer
native record or automatically expand the experiment.

Launch detached and return control without polling. The user requests status;
independent audit and regression wait for a subsequent instruction. Passing
capture checks, if achieved, still do not qualify native integration convergence,
input-sampling convergence, biological recovery, GPU execution, restart,
whole organs or general BETSE parity. Preserve the distinction between a
program-to-program comparison and validation against experimental biology.
