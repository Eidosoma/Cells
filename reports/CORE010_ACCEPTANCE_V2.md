# CORE-010 acceptance resource amendment v2

2026-09-11; closeout inspected 2026-09-12. Status: bounded development acceptance complete. Stable production remains
0.14.0; all 51 development production modules remain byte-identical at 0.15.0.dev0.

The [separate full audit](core-010-v2-full-audit.json),
[4190-test six-context matrix](core-010-regression-03/verification.json) and
[development closeout](core-010-v2-closeout.json) all pass. The detached follow-up
finished September 11 at 22:31 UTC in 2154.841 seconds. All tests passed without
failures, errors or skips. The closeout authenticates 733 of 740 baseline files
unchanged and seven intended prior edits; it does not promote a stable release.

The [new protocol](../docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE_V2.md) and
[resource definition](../configs/acceptance/spatial_extracellular_resources_v2.json)
register a two-hour wall cap with the unchanged 2-GiB limit, CPU 0–3, four eager
lanes, case order and scientific panel. The [timing projection](core-010-runtime-projection.json)
estimates 87.3 minutes under comparable conditions; it is not a runtime guarantee
or compiled/GPU performance measurement.

The [first stopped attempt](CORE010_ACCEPTANCE.md), its 880 files, all subset
audits, original protocol and previous closeout remain unchanged. This is a new
complete-panel attempt, not reuse or relabeling of old trajectories.

All **106 new resource/byte-replay tests pass** in 4.97 seconds with warnings
treated as errors ([receipt](core-010-retry-preflight-01.xml)). All **228 combined
audit/resource preflight tests pass** in 61.23 seconds with warnings as errors
([receipt](core-010-retry-preflight-02.xml)). Lint and formatting pass for 284 files.
The new tests check named profile selection, changed-resource refusal, worker
context, both wall limits, unchanged artifact limits, registration before work,
failure retention, non-overwriting output and all 73 fields' signed-zero bytes.

Resource-profile selection is explicit in the shared acceptance driver, artifact
auditor and closeout. Workers obtain their profile from the saved registration;
no module-global plan mutation or arbitrary CLI timeout is used. The existing
exact comparison now enforces dtype, shape and bytes explicitly, including
signed zero. Tolerance-based comparisons and all physical checks are unchanged.

The [pre-edit baseline](core-010-retry-workspace-baseline.json) captures 740
pre-existing workspace files and authenticates the previous 4084-test result and
tooling closeout. Planned existing edits are three acceptance scripts and four
status documents; the scientific plan, fixtures, reference, independent physical
oracle, production code and all earlier evidence must remain unchanged. The
[prelaunch check](core-010-v2-prelaunch.json) authenticates 733 unchanged files and
exactly those seven intended edits, with none missing.

The new [acceptance-02 registration](../runs/core-010-2026-09-11/acceptance-02/registration.json)
captures 352 implementation/protocol/evidence files and all 42 scalar definitions
before execution. Capture started at approximately 19:21 UTC with a 21:21 UTC
hard deadline. All captured files remain frozen through acceptance and regression.
The [capture result](../runs/core-010-2026-09-11/acceptance-02/verification.json)
passes in **4381.787 seconds (73 minutes)**: 57 scalar runs, 12 streams,
53 comparisons and 912 payload files. All fourteen eager cases completed.
This is the complete in-run verdict, not the separate audit/regression closeout.

At the user's request, assistant polling stopped while the existing capture
continued in its own OS session (PID/session 1709422, no controlling terminal).
The computation was not killed, restarted or resumed from an invented checkpoint.
The capture subsequently finished within its registered two-hour cap and wrote
its verification artifact. The user has now requested the remaining closeout
and a careful first BETSE comparison; the [detached handoff](CORE010_CLOSEOUT_HANDOFF.md)
records that follow-through. No assistant polling or automatic retry is scheduled.

The first completed overlap check passes: all **2044 arrays across 28 compiled
and refined runs match v1 byte-for-byte**, including dtype, shape and signed zero
([read-only receipt](core-010-v2-compiled-repeat.json)). Those are newly computed
v2 trajectories compared with retained v1 output, not reused v1 results. This
subset comparison alone did not qualify the other execution paths; the complete
v2 capture now records them and its independent full-panel audit passes.

Those three follow-up gates are complete. Before external comparison work,
[REF-003a preservation](ref-003a-preservation.json) reauthenticated the 912 payloads
and existing 352-file source capsule without rerunning the solver. The subsequent
[passive-law contact](REF003A_PASSIVE_CONTACT.md) is a separate component result,
not additional spatial acceptance. Stable promotion is separate. No optimization,
GPU, organ, new physiology, BETSE trajectory parity or biological validation is
claimed by CORE-010.
