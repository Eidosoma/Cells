# REF-005d R0: independent saved-output review launch

2026-09-17, D129. Following the passing D128 producer qualification, the user
authorized its independent review. The [frozen contract](REF005D_LIVE_AUDIT_HANDOFF.md)
and [reviewer](../validation/betse/live_recording_audit/README.md) make no changes
to production or the saved qualification. Neither simulator is run.

## Software gate

**97 checks pass in 15.33 s**; complete source-bound check **15.795 s**.
The passing packet binds **21 reviewer/helper inputs**, **285 sealed files**
and **23 internal software-test aliases**. Lint and formatting checks pass.

Tests exercise actual saved checkpoint-heavy probe/matrix cases, a finer-step
case and both eager/compiled sparse cases; an actual native row and observer
pair; handwritten bit fixtures; resealed checkpoint, index and chunk corruption;
receipt/resource/coverage refusal; complete prerequisite authentication;
source/registration guards and detached launch/failure handling.

Preserve earlier software attempts: **82 passes / six failures** exposed a new
review-controller import-name collision and a source-count/schema assumption;
**88 passes / one failure** exposed a recorded internal file alias in the older
preflight packet. Fix only the new reviewer and add regressions. The uniquely
named controller is checked explicitly; software aliases must be internal,
registered and exactly present. Normal artifact paths still reject links.
No simulator or accepted producer source is changed to obtain a pass.

[Software completion](../runs/ref-005d-live-audit-2026-09-17/software-03/completion.json):
`66d8a0e4f7002171632adf3360929324af70d085859cbab8afaa1bc312005b92`.
[Passing XML](ref-005d-live-audit-checks-03.xml):
`ac3a0d077500caff23bda9463877a88c809c1b12e61bdd2abd8e141de46d7316`.

## Full review

Target: `runs/ref-005d-live-audit-2026-09-17/audit-01`.

Authenticate D128's **516 sealed payloads / 520 regular files / 680 frozen
inputs**, the **964 native / 24 stopped-continuation files**, and the complete
accepted numerical/codec prerequisite chain. Compare 36 live native streams
with original JSON and eighteen observer pairs. Independently inspect all
saved Cells baselines, recording chunks and complete checkpoints/restart
suffixes for the separate probe and full 24-case matrix.

For unsaved in-memory windows, reconstruct expected rolling receipts from
accepted baselines. This covers 72 matrix window runs, six restart windows,
six zero-length cases and two sparse controls, plus the separate probe paths.
These are **receipt-based checks**, not direct decoding of unsaved trajectories.
No new physical-law evaluation, independent native memory measurement, longer
horizon, biological validation or GPU evidence is produced.

Bounds: CPUs 0–3, one BLAS thread, **900 s / 4 GiB address space / 8 MiB per new
file / 64 MiB new artifacts / 1 GiB free-disk reserve**. Caps are not an ETA.
Before/after source and prerequisite checks, per-row/case reports, durable logs
and terminal completion/failure. No polling, automatic retry or follow-up job.

## Launch acknowledgment

Launched **2026-09-17 17:18:03.643 UTC**, PID **3503584**, at the target above.
Registration SHA-256:
`4b8cb8f0e4eb919c4930b40f2b7b8702ab8fd2bc96e45e39de6ca9d23da0eb55`.

The launcher authenticated the passing source-bound software result and full
prerequisite inventories, wrote the registration and source capsule, and
returned successfully. No worker status/completion poll was performed.
This acknowledgment is not an independent-review pass. Await the user's status
request; no automatic follow-up campaign is authorized by completion.

## Subsequently reported completion

At the user's status request, the independent review had **passed**, finishing
at **17:20:12.570 UTC** in **128.769 s**, with zero failed comparisons. All 66
sealed payloads, 70 regular files, 21 frozen inputs, source-bound software and
prerequisite inventories authenticate. The complete counts and evidence limits
are recorded in the separately authorized [D130 closeout](REF005D_LIVE_CLOSEOUT.md).

Completion SHA-256:
`769994fac30ba99e64bc5c3f998c49e9d1c747c3a2e9bbeb5fadd2c57febb647`.

No automatic follow-up occurred. The next user instruction authorized preparation
of the separate [10 ms reference-only study](REF005E_REFERENCE_SCOPE_HANDOFF.md).
