# D076 / REF-003e0: saved-pilot audit handoff

2026-09-12. **65 new evidence preflight tests pass; the independent numerical
audit and combined regression run separately, detached.** This report records
the launch boundary, not a completed audit or a new simulation.

## Completed capture and preservation

The D075 pilot finished in **26.138807266 seconds** at 21:21:16 UTC: all twelve
native runs, six observer-off comparisons and four profile/no-op comparisons
passed their capture gates. It retains 240 observed steps/dispatches, 80 with
zero-amplitude targeted events enabled, and no recorded Python warnings. The
expected ignored-cutting diagnostic remains in its log. The experiment is still
only matched constants, 25 µs, 1 ms, seven neutral-prepared cells and a finite
bath, with passive or blocked membranes.

The source/capture [contract](../docs/BETSE_FULL_LOOP_BRIDGE.md) and historical
[launch handoff](REF003E0_FULL_LOOP_PILOT.md) remain unchanged. All 142 pilot
files are preserved, with 138 finalized payloads and a 58-file capsule.
Before its capture receipt, retained artifacts occupied 49,352,173 bytes.

Capture SHA-256:
`0bf8f5674a6b92af01171f95bab652d5c0cbfd8033d174d339fac9777a283b12`.
Registration SHA-256:
`1b6105df591e482697950feeac9b43f0228ae22038273c3f8c5284a6c6f90d82`.
Source capsule SHA-256:
`0baa5e0a5e6b4482206dc4b96d07790c769e28815e66bcb5e1dc710e0976ac45`.

The [new preservation receipt](ref-003e0-loop-audit-preservation.json) records
903 existing workspace files. Only seven existing status documents change;
all 352 accepted implementation files / 51 production modules and the complete
earlier evidence chain remain unchanged.

## Prelaunch verification

All **65 new tests pass in 16.47 seconds**, with no failures/errors/skips, in
[the first preflight receipt](ref-003e0-loop-audit-checks-01.xml). They inspect
actual saved setup/event/step links and try rehashed corruptions of metadata,
arrays and capsules, plus missing payloads, links, import and timeout gates.
No model integration or complete independent numerical audit occurs in this
preflight. The source tree passes lint/format checks across 337 Python files.

The [audit contract](../docs/BETSE_FULL_LOOP_AUDIT.md) and
[prelaunch receipt](ref-003e0-loop-audit-prelaunch.json) bind the separate driver,
checker, tests and resource plan. The audit recomputes **88,956 numerical
comparisons** with the frozen independent routines and original tolerances;
it neither imports either simulator nor loads native pickles. It independently
checks capture integrity, physical/control links and native boundary semantics,
without calling the capture checker.

## Detached execution boundary

The [launch receipt](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/launch.json)
records actual launch and PID. Two stages run: the numerical audit, then
**165 focused tests** (D075's 100 plus the new 65). Limits are 90 seconds per
stage, 210 seconds overall, CPUs 0–3 and 64 MiB retained output. Logs, numerical
results, JUnit and completion/failure manifests are durable. The source capsule
contains the unchanged 58 pilot files plus four new audit/test files.

Only a successful audit, combined regression and preservation/resource closeout
can create a new narrow-pilot qualification. The original capture remains
unchanged and explicitly pending independent audit in its historical receipt.
The user requests the next status check; there is no automatic polling, retry,
expanded capture or intervention. No old full adapter suite, 4190-test matrix,
new Cells run, biology, restart, GPU or release promotion is included.
