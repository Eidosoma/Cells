# REF-003e1: audit the rejected held-input response

2026-09-13, D082. **Saved-data audit implementation, not a new simulation or
response qualification.** The complete audit/regression runs separately and
detached. This document precedes that execution; see the
[handoff](../reports/REF003E1_RESPONSE_AUDIT_HANDOFF.md) for software evidence.

## What the original capture found

The [D081 packet](../runs/ref-003e1-response-2026-09-13/capture-01/failure.json)
completed eight native and 24 Cells runs in **715.769 s**, without Python
warnings. Comparison then rejected **150 of 345,576 checks** under unchanged
criteria. All 150 files, including the 88-source capsule and 146 manifested
payloads, remain intact. There is no passing capture receipt.

The saved report separates the scopes as follows:

| Scope | Comparisons | Failed |
| --- | ---: | ---: |
| Internal controls, laws and accounting | 198,264 | 0 |
| Fixed-input Cells refinement, backends and cross-engine surfaces | 147,312 | 150 |
| Whole original comparison | 345,576 | 150 |

Cross-engine failures are 34 per backend for baseline and zero amplitude,
seven per backend for suppression/recovery, and zero for static blocking.
The largest normalized error is **2.239768**, on the baseline shared-bath K
amount increment at 1 ms. The saved finer-step constant-input baselines provide
a useful timestep diagnostic, not permission to replace the rejected result.

## Two checks, with different independence claims

The new [offline auditor](../validation/betse/response_audit/response_audit.py):

1. Authenticates original registration, sources, every file, native package,
   Cells implementation/runtime, row coverage and execution chronology.
   It does not deserialize native pickles or import either simulator, NumPy
   or JAX. A runtime import fence enforces that boundary.
2. Replays the entire original comparison using its **frozen arithmetic
   helpers**, requiring exact equality with the original numerical report.
   This checks reproducibility; shared helpers are not a second independent
   derivation of the physical laws.
3. Independently reconstructs the comparison surfaces from saved raw native
   concentrations/densities and Cells histories/observations. It uses separate
   owner aggregation, amount/current conversion, cumulative summation and error
   normalization, not the frozen surface/comparison helpers. It checks all
   36 scopes / 147,312 comparisons and retains all 150 failing identities.
4. Requires the original first 100 failures, worst failure and normalized
   maximum to match exactly. Diagnostic transfer maxima allow only declared
   summation-roundoff differences (`fsum` versus sequential accumulation).
   Every physical pass/fail comparison still uses the original criteria.

The new failure ledger labels time, backend, condition, shared compartment and
Na/K species. No failed comparison may disappear, change scope or be silently
reclassified as a success. State/ledger boundaries, interval transfers and fresh
rates stay distinct; no native endpoint RHS is invented.

## Reporting correction, not numerical correction

The frozen checker's `summary()` retains a reference to a mutable failure list.
The internal-law summary is made before later cross-engine checks append their
failures. Its count correctly says zero failures, but its saved list incorrectly
contains the later cross-engine failures. The overall 150-failure decision is
unaffected.

Reproduce this alias with a small synthetic check and verify it in the exact
original replay. A new reporter takes a deep value snapshot. A separate,
versioned `corrected-comparison.json` changes only
`internal_laws.first_failures` to an empty list, with original provenance and
an explicit changed-field list. The original checker, comparison and failure
receipt are **not edited**. The corrected review still says rejected.

## Preserve the user's operational edit transparently

During audit preparation, user commit
`fa5ec7127cfb0062e1151904b90f25a38b3e9bd5` added `reports/ref-*.xml` to
`.gitignore`. That changes repository bookkeeping, not captured scientific
data. The old D081 preservation test correctly rejects this pre-existing edit.
Do not revert the user's commit or weaken the frozen test.

The [new preservation record](../reports/ref-003e1-response-audit-preservation.json)
pins **969 baseline files and all 150 capture files**. It authenticates the exact
old/new ignore-file hashes and added bytes, permitting no arbitrary metadata
changes. The union with old manifests keeps now-ignored XML receipts protected.
Only the seven existing status documents may be edited by this audit work.
All 352 accepted files / 51 production modules remain unchanged.

Run all original 122 tests unchanged. Record the expected **121 passing / one
failing historical metadata guard** as a non-green legacy result, with exact
test identities and failure reason. Any extra/different failure, error or skip
blocks closeout. Separately require every new audit test to pass. This explicit
operational amendment is not scientific tolerance tuning or a skipped test.

## Closeout and next boundary

The detached job performs audit, legacy regression and new regression in that
order. A successful closeout is named `failure_audit_closed_response_rejected`:
it verifies a failure, not a passing response. Persist logs, source capsule,
corrected review, full failure ledger and JUnit outcomes; stop on unexpected
failure without retry or polling. No production matrix is rerun.

The [next refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md) distinguishes
native integration error from changing the sampled input. It is design only;
no follow-up response, longer horizon, active physiology, biology, organ or GPU
qualification is launched or implied by D082.
