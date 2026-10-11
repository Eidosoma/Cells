# REF-003e0 expanded audit: prelaunch handoff

2026-09-12, D078. This document records preparation and the detached launch
boundary, not the final arithmetic/regression verdict.

## Completed capture

The user-polled [D077 capture](../runs/ref-003e0-expanded-2026-09-12/capture-01/capture.json)
passed its controls in **203.562 s**. All **72 native runs / 3360 observed steps**,
36 observer pairs, 24 variant comparisons, 1120 enabled-target zero-amplitude
dispatches and 12 original-pilot overlaps are present. There are no Python
warnings. All 798 payload hashes and the 802-file layout were checked at status.
Output before the receipt is **644,923,963 bytes**, within prospective limits.

Capture SHA-256:
`0f71ad7752585fa2b82e00448664f55c5d265d7502089dac6a9c08c26ea4f63b`.
Registration SHA-256:
`1c25ce10d09cb5f564effcd70a06c0debe4904671430bb6a7cbfe1f6b13e0e71`.
The capture remains `capture_controls_pass_pending_independent_audit`.

## Separate audit preparation

The [independent contract](../docs/BETSE_EXPANDED_AUDIT.md) checks all saved
state/event/lifecycle/control links and **1,232,616 numerical comparisons**
using the original independent arithmetic and tolerances. It imports neither
model nor NumPy/JAX, calls no capture checker and does not load native pickles.
It derives expected input metadata separately and keeps actual entry charge
matched to the row's F/R and timestep. It processes one control group at a time.

The [preservation baseline](ref-003e0-expanded-audit-preservation.json) contains
922 workspace files, all 802 expanded capture files, the original 142 pilot
files and its 11 audit-job files. All 352 accepted Cells files / 51 production
modules are unchanged. Only seven pre-existing status documents may change.
Four new Python modules add the independent audit, context, detached job and
actual-evidence tests. Older source/receipt files remain frozen.

The [first preflight](ref-003e0-expanded-audit-checks-01.xml) retained 141 passes
and two fixture setup errors in 49.07 s: hard links from the capture to `/tmp`
crossed filesystem boundaries. All actual row/control checks passed. The
fixture now creates temporary links beside, never inside, the frozen packet,
unlinks before mutation and cleans up only its own temporary directory. No
captured data, audit criterion or numerical code changed to address this issue.

The [corrected focused test receipt](ref-003e0-expanded-audit-checks-02.xml)
passes **all 143 tests in 48.73 s**. Quality checks pass across **345 Python
files**. The [prelaunch receipt](ref-003e0-expanded-audit-prelaunch.json) binds
these checks, resource estimate and final source hashes. Preflight tests are
not the full numerical audit or formal trajectory qualification.

## Detached closeout

The job runs the offline audit, then the five-module focused regression:
the prior 290 D075–D077 tests plus 143 new D078 tests, **433 total**. Its capsule includes
all 67 capture sources and the four new files. No native/Cells capture, older
full adapter suite or production matrix is rerun. Prospective resource limits
and their measured basis are in the prelaunch receipt/job plan: estimates of
147 seconds per stage and 11,628,348 new bytes fit **180-second stage /
420-second total** and **64 MiB** limits. CPUs remain 0–3 with single-threaded
numeric libraries; there is no GPU, peak-RAM or performance-parity claim.

Fresh destination: `runs/ref-003e0-expanded-audit-2026-09-12/audit-01`.
The [launch receipt](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/launch.json)
records actual launch/PID; this handoff does not infer process or completion
status. Output is durable audit/regression logs and either a joint completion
or failure receipt. Do not poll or retry automatically.

Only successful independent arithmetic and focused regression closeout qualify
the registered 1 ms, seven-cell, both-constant-set/three-timestep zero-amplitude
SIM bridge. A subsequent nonzero held-drive experiment needs its own design,
registration and user instruction. No biological, organ, restart, GPU,
family-wide feature-parity or stable-release claim is made here.
