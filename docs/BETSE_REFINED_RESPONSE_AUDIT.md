# REF-003e1 independent finer-response closeout

2026-09-13, D086. Saved-data audit and focused regression, not another simulation.
The user reviewed D085's completed continuation and requested the next step.
See the [handoff](../reports/REF003E1_REFINED_AUDIT_HANDOFF.md) and
[job plan](../validation/betse/response_closeout/refined_audit_plan.json).

## Evidence being reviewed

The [D085 capture](../runs/ref-003e1-trace-resume-2026-09-13/capture-01/capture.json)
completed all 22 remaining Cells runs and comparison in 2239.322 s. Together
with the unchanged partial D084 attempt, it supplies 16 native / 48 Cells runs
at 12.5 and 6.25 µs. The older coarse packet supplies eight native / 24 Cells
runs at 25 µs. The continuation used 325,843,874 combined retained-plus-new
artifact bytes before its final receipt, within the registered limit.

The saved comparison reports 2,494,936 scalar checks, including 2,298,936 required
checks with no failures (maximum normalized error 0.5592883878208624). Its 4173
diagnostic failures comprise 150 coarse cross-engine checks, 40 intermediate
cross-engine checks and 3983 across-input-hold checks. Those failures remain
failures, not exceptions removed from the total.

Preserve all 56 continuation files, all 241 files in the resource-failed attempt,
the older coarse response/audit/dispatch packets, the exact ignore-rule amendment,
and the 1027-file pre-edit baseline. Only the seven established status documents
may change. All 352 accepted implementation files / 51 production modules,
original definitions, numerical criteria and previous adapters stay unchanged.

## Independent and replayed checks

First authenticate the full source/receipt chain and exact file coverage. Verify
timestamps, worker identity, native installed-source hashes, CPU/float64 metadata,
runtime resource probes, row coverage and artifact accounting. Keep the 26 reused
Cells rows associated with their original registration and paths; no old aggregate
Cells worker receipt is invented. Verify the 22 newly captured rows separately.
Read all data in place: no copies, relabelling or executable native pickle loads.

Replay the complete frozen D085 checker and require exact equality with its
saved comparison, excluding only its worker bookkeeping fields. This rechecks
1,373,032 internal law/accounting comparisons using the existing model-free
high-precision helpers and preserves the exact old coarse rejection.

Separately reconstruct all 1,121,904 surface comparisons over 132 scopes. This
uses D082's independent saved-array readers and `fsum` reconstruction of native
cumulative transfers, with a new variable-grid comparator and scope assembly.
It does not call the original surface builders, comparison loops, projection or
verdict helper. The full check covers:

- All 41, 81 and 161 state/ledger boundaries at the three holds.
- All interval-start rates/currents and all interval transfers.
- Fixed-input Cells solver subdivisions and eager/JIT comparisons at every hold.
- Cross-engine comparisons at every hold, with only the finest hold required.
- Exact 41-boundary projections for across-hold diagnostics, without interpolation.

There is no invented native terminal rate. Cells' separately recorded final RHS
remains validated against the last retained input hold by the frozen arithmetic.
The 925,904 required independent surface checks plus 1,373,032 replayed internal
checks must account for all 2,298,936 required checks.

Every independent physical comparison uses the original absolute/relative limits
and expected-value normalization. For diagnostic agreement between independently
reconstructed values/maxima and the old report only, retain D082's summation
roundoff allowance (relative 2e-11, absolute 2e-20). This never relaxes a physical
pass/fail threshold. Independent normalized maxima are reported separately;
the frozen replay preserves all original summaries exactly.

Write all 4173 failures to a full ledger, with scope, quantity, column, time and
interval endpoint where applicable. Require unique, in-range coordinates, exact
per-scope counts, unchanged required/diagnostic classifications and agreement
between the ledger and every reported first-100 example list. Count truncation
and diagnostic failures must not be hidden by a passing required-gates headline.

## Software, source and resource gates

Five new Python modules plus one plan live under `response_closeout/`, making a
118-input capsule. The frozen D085 112-input capsule and older flat 88-source
inventory stay unchanged. No new runtime dependency or production change.

The first preflight retains 94 passes / one failure in 25.53 s: a new import-fence
test expected the wrong exception type. The existing guard correctly raises
`RuntimeError`. Correct only the new test expectation, preserve its receipt, and
add complete loader/ledger/closeout linkage tests. All 105 checks now pass in
28.38 s, and all 385 Python files pass whole-tree lint/format checks.

Selected actual baseline/pulse surfaces exercise the three full grids and both
across-hold transitions. Synthetic tests exercise the entire scope layout, late
grid corruptions, exact source routing, incomplete/duplicate ledgers, rehashed
receipt corruption, strict test identities, detached launch and timeout retention.
Synthetic data is not numerical evidence for the real panel, and these short
tests do not replace the full detached numerical audit.

The joint job runs the 231 existing D082/D084/D085 tests unchanged plus the 105
new tests: 336 exact identities, with no failure/error/skip permitted. This is
a focused adapter regression, not a rerun of the whole simulator acceptance
matrix. D082's historical 121-pass / one expected metadata-guard rejection remains
preserved; it is not relabelled green or included as a passing suite here.

Prospective limits: CPU 0–3, single-thread numerical libraries, 300 seconds for
the audit, 300 seconds for regression, 900 seconds total. New audit artifacts
are capped at 64 MiB, with OS-enforced 16 MiB individual worker files. These
are file limits, not trace-memory or process-RAM limits. No peak RAM is measured.
Measured saved-comparison and test durations plus allowances estimate 217/252
stage seconds. The output estimate is 11,222,792 bytes, below both the aggregate
limit and the individual-file limit even if all estimated output were one file.
Original simulation packets are inputs and are neither copied nor rewritten.

## Qualification and handoff

The standalone numerical audit reports passing evidence **pending regression**.
Only a joint completion may set `finest_held_response_qualified: true`, bound to
the explicit seven-cell, 1 ms, matched-constant, four-condition, 6.25 µs held-input
scope with the declared CPU backends/subdivisions. All other qualification flags
remain false: native convergence, forcing convergence, biology and GPU.

Agreement under one corresponding held input is not convergence as that input
is resampled. The 3983 across-hold failures remain pertinent limitations. Likewise,
this does not establish general BETSE parity, organ-scale validity, active-channel
coverage, restart correctness or a new stable release.

Intended fresh destination:
`runs/ref-003e1-refined-response-audit-2026-09-13/audit-01`.
Launch once detached with durable stage logs, result/failure files and a frozen
source capsule, then return without polling. Only actual launch/completion/failure
receipts establish state. No automatic retry, simulation, refinement expansion
or subsequent job follows. Review the result on the user's next instruction.

For the multiscale design, keep two separate contracts: accuracy of integration
under a specified interface input, and sensitivity to the rate at which that
input is exchanged or sampled. This audit does not change either contract to
obtain a passing comparison.
