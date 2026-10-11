# REF-003e1 / D086 independent finer-response audit handoff

2026-09-13 UTC. Implementation/prelaunch handoff; full audit execution is separate.
See the [contract](../docs/BETSE_REFINED_RESPONSE_AUDIT.md),
[context](../validation/betse/response_closeout/refined_audit_context.py),
[independent surfaces](../validation/betse/response_closeout/refined_audit_surfaces.py),
[audit](../validation/betse/response_closeout/refined_audit.py) and
[detached job](../validation/betse/response_closeout/refined_audit_job.py).

The user-reviewed D085 capture completed in 2239.322 s. It reports all 22
remaining Cells runs completed, 2,298,936 required comparisons passing and 4173
diagnostic failures retained within 2,494,936 total checks. The largest required
normalized error is 0.5592883878208624. This is capture evidence pending independent
audit, not a completed convergence or biological validation claim.

Authenticate and preserve the 56-file continuation, 241-file original resource
failure, original 26 reused Cells / 16 native runs, older coarse evidence and
all previous source/receipt chains. The
[new preservation receipt](ref-003e1-refined-audit-preservation.json) captures a
1027-file baseline. Only seven established status documents may change; all 352
accepted implementation files / 51 production modules remain unchanged. Reused
rows remain at their original paths, with no invented old Cells worker receipt.

The first [preflight receipt](ref-003e1-refined-audit-checks-01.xml) retains
94 passes / one failure in 25.53 s. The new test expected the wrong exception
from the existing import guard; that guard correctly rejected the import.
Correct the new test, not the guard, and add full-loader/ledger/output-linkage
coverage. All [105 new checks pass](ref-003e1-refined-audit-checks-02.xml) in
28.38 s. All 385 Python files pass lint/format checks. The first receipt's hash
is pinned and both receipts are frozen at prelaunch.

These short checks include selected actual full-grid baseline/pulse comparisons
and explicitly synthetic scope/negative-evidence fixtures. They do not stand in
for the full actual audit. The new five-module/one-plan extension supplies a
118-input capsule, preserving the old 112 inputs and the flat 88-source inventory.

The detached audit must:

1. Verify immutable packet coverage, worker/source/runtime metadata, separate
   old/new row provenance, chronology and actual resource accounting.
2. Replay the frozen complete comparison exactly: 2,494,936 checks, including
   1,373,032 model-free internal law/accounting checks and the old coarse rejection.
3. Independently reconstruct all 1,121,904 surface checks / 132 scopes using the
   separate saved-array/`fsum` route, with 925,904 required surface checks passing.
4. Preserve a full, linked ledger of 4173 diagnostic failures: 150 coarse, 40
   intermediate and 3983 across-input-hold. No physical tolerance changes.
5. Run the exact 336-test focused regression: 70 D082, 114 D084, 47 D085 and
   105 new tests. Require all identities once, with zero failures/errors/skips.

D082's separate historical 121-pass / one expected metadata-guard failure stays
preserved, not rerun or relabelled an all-green result. No whole-simulator
acceptance rerun, production amendment or new dependency is in scope.

Prelaunch: `ref-003e1-refined-audit-prelaunch.json`, created only after software
checks, preservation and whole-tree quality gates pass. It binds both new test
receipts, all expected regression identities, the source capsule and documents.

Resources: CPU 0–3, single-thread libraries, audit/regression stage limits
300/300 s, total 900 s (15 minutes), 64 MiB new audit artifacts and OS-enforced
16 MiB worker files. Estimates with allowances are 217/252 stage seconds and
11,222,792 bytes. File caps are distinct from trace-memory and total process RAM;
no peak-RAM or GPU measurement is claimed. Original simulation artifacts are
read in place, not copied into the output budget.

Intended fresh destination:
`runs/ref-003e1-refined-response-audit-2026-09-13/audit-01`.
Only its `launch.json` establishes launch; `completion.json` or `failure.json`
establishes completion. This handoff does not assert either. Return after a
single detached launch without polling. Failures retain partial outputs; no
automatic retry, simulation, expansion or subsequent job.

Only a successful joint numerical-audit/regression completion may qualify the
explicit finest-held-input response scope: seven cells, 1 ms, matched constants,
four controls, 6.25 µs held input, and the declared CPU backends/subdivisions.
Native/forcing convergence, biology, GPU, general BETSE parity and organ-scale
claims remain unqualified. Review the actual receipts on user instruction.
