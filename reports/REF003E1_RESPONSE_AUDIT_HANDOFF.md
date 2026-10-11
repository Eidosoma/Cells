# REF-003e1: rejected-response audit handoff

2026-09-13, D082. **Prelaunch software evidence; complete audit/regression
results are separate.** No simulator is rerun and no physical tolerance changes.

The [original capture](../runs/ref-003e1-response-2026-09-13/capture-01/failure.json)
finished eight native and 24 Cells runs in **715.769 s**, then rejected 150 of
345,576 comparisons. A mutable failure-list alias contaminates only the internal
summary's displayed list, not its count or the overall rejection. Preserve that
packet and checker; add a separately versioned corrected review.

The [audit contract](../docs/BETSE_HELD_RESPONSE_AUDIT.md) distinguishes exact
frozen-law replay from an independently rebuilt 147,312-comparison surface
check. Require all 150 failures in a full ledger. The saved constant-input
baseline ladder is diagnostic only; the [future refinement design](../docs/BETSE_HELD_RESPONSE_REFINEMENT.md)
does not launch another experiment or establish pulse convergence.

## Software evidence and preservation

All **70 new focused tests pass in 12.01 s** in
[checks-01](ref-003e1-response-audit-checks-01.xml), with warnings as errors and
no failures/errors/skips. They check saved data, structural/semantic corruption,
immutable report snapshots, unchanged rejection criteria, baseline diagnostics,
failure classification, exact legacy-test identities, import boundaries,
detached launch and durable failures without retries. Neither model is run.

The [preservation record](ref-003e1-response-audit-preservation.json) pins 969
baseline files and all 150 capture files. All 352 accepted implementation files /
51 production modules and the original flat 88 adapter inputs remain unchanged.
Four new nested audit modules make a separate **92-file source capsule** without
changing the historical adapter inventory. Only seven existing status documents
are updated. All **363 Python files** pass whole-tree lint/format checks; that
evidence is bound by the prelaunch receipt.

The user independently added `reports/ref-*.xml` to `.gitignore` in commit
`fa5ec7127cfb0062e1151904b90f25a38b3e9bd5`. The exact before/after hashes and
added bytes are recorded; newly ignored old XML evidence remains pinned. The
original 122-test regression will run unchanged and is expected to report
**121 passes and one historical preservation-guard failure**. This is explicitly
not an all-green legacy suite. Any different/additional failure blocks closeout;
the new 70-test regression must be entirely green. No test is skipped or patched
to hide the user's operational change.

## Prospective resources and detached execution

The [prelaunch receipt](ref-003e1-response-audit-prelaunch.json) binds source,
test, documentation and preservation hashes before registration. Estimates use
the saved 6.774 s comparison, 21.402 s historical test receipt, current 12.004 s
new-test receipt and explicit allowances: **44 / 48 / 34 seconds** for audit,
legacy regression and new regression. These are estimates, not completed stages.

Stage caps are **90 / 90 / 120 seconds**, with **360 seconds total**, CPUs 0–3,
single-thread numeric libraries, **16 MiB total artifacts** and OS-enforced
**8 MiB per worker file**. Aggregate bytes are checked between stages and before
closeout; this is not a filesystem quota or a peak-RAM measurement. The original
56 MB capture is read in place, not copied or rewritten.

Intended fresh output: `runs/ref-003e1-response-audit-2026-09-13/audit-01`.
Exclusive registration/source capture precedes launch; the separate `launch.json`
records actual PID/time. This handoff is not a launch or completion receipt.

The job writes `audit.json`, `corrected-comparison.json`, `failure-ledger.json`,
stage logs, legacy and new JUnit receipts, plus either `completion.json` or a
durable `failure.json`. Successful closeout means
`failure_audit_closed_response_rejected`, never a qualified physical response.
Launch once detached, return control and let the user request status. No automatic
polling, retry, refinement, production acceptance, biological or GPU claim.
