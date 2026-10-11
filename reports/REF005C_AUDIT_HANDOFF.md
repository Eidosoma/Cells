# REF-005c independent refined-pilot review handoff

2026-09-16, D120. **Audit preparation, not independent acceptance.**

The D119 capture finished in **501.812 s** and reports **616,806 comparisons,
zero failures**, 36 native runs, eighteen observer pairs and twelve exact overlap
records. All 36 refinement groups pass the producer's criteria. Its completion
remains `refined_pump_pilot_pass_pending_independent_review`.

Capture: `runs/ref-005c-refined-pump-2026-09-16/refinement-01`.
Registration SHA-256:
`1dcfb80dc010bc694bf752caa0b72c0f97699e162f4aa3599bfc5258deec9c07`.
Completion SHA-256:
`45bc4adf9986bf4adc9750af969818b1cf4e0466854e01dbf136e02eb23cba6f`.

The main native energy-balance defect is now approximately **7.351e-8 pJ**,
below the unchanged **1e-7 pJ** criterion. This supports the diagnosed finite-step
error explanation, but the producer report is not itself independent closure.
The original six-miss attempt and its [diagnosis](REF005C_PILOT_FAILURE_DIAGNOSIS.md)
remain rejected and unchanged. The [refinement contract](../docs/BETSE_PUMP_REFINEMENT.md)
is not amended by this review.

## Independent checks

The new `validation/betse/pump_pilot_audit` package reads saved numbers only.
An import fence excludes Cells, BETSE, NumPy, SciPy, JAX, the reference solver,
and both producer comparison paths. Native pickle files are hashed, never
executed. Existing independently tested stdlib readers and 70-digit arithmetic
are reused, with their exact sources included in the new review capsule.

- Authenticate all **641 captured inputs / 55 production modules / 444 sealed
  payloads** and the four terminal/launcher/log files. Check the original
  431-file rejected packet, diagnosis, native lifecycle and prerequisite receipts.
- Verify the scientific contract against the original registration and all
  **213 byte-identical reused files**. Decode the original 24 Cells NPZ
  trajectories, six full-state restart suffixes and six complete checkpoints;
  those files must match their copied counterparts exactly.
- Inspect every one of the **6,720 observed native updates** and its lifecycle,
  live inputs, raw pump/passive returns, applied density, transfer ownership,
  cumulative conservation, electrical state, clocks and saved history links.
  The physical-record count is **20,178** (initial plus three stage records).
- Reconstruct native energy and every recorded canonical state using independent
  70-digit total-flux accounting and potassium-derived pump cycles. Cross-check
  every producer-reconstructed state/voltage coordinate at roundoff-only bounds.
- Re-evaluate all registered native/reference, Cells/reference, cross-engine,
  backend, saved-accounting and floor-aware refinement gates. Verify all twelve
  overlap records and eighteen observer pairs with signed-zero-preserving digests.
- Report the convex chemical/capacitive remainder as a diagnostic only: never
  subtract it from the energy defect, change dissipated energy, or relax a limit.
  Count all 72 known disabled-cut notices explicitly; do not claim warning-free
  execution.

The accumulated native material allowance is exactly the already-registered
step-count/inventory policy. It is never applied to raw flux or trajectory limits.
Cells energy diagnostics remain source-bound saved reports in this review;
their separate D114 independent family accounting is preserved, not relabeled as
a new reconstruction of every Cells trajectory here.

## Execution boundary

**47 preflight checks pass in 30.06 s**, recorded in
`reports/ref-005c-audit-checks-01.xml`. They cover exact evidence authentication,
unchanged scientific criteria, blocked model/producer imports, malformed paths
and records, all six saved short controls, one complete actual 640-step refined
control, all saved Cells/checkpoint links, acceptance/resource guards, known
notices and detached single-launch behavior. These are software/reader checks,
not completion of the full independent review.

```text
.venv/bin/python -B validation/betse/pump_pilot_audit/audit_job.py launch runs/ref-005c-refined-pump-audit-2026-09-16/audit-01 --tests reports/ref-005c-audit-checks-01.xml
```

One detached process, CPUs **0–3**, one BLAS thread, stdlib calculations and
**900 s maximum**. Hard **32 MiB/file**, checked **128 MiB audit artifacts**;
the approximately 1.47 GiB original capture is read in place, not copied again.
Freeze the review code, helper dependencies, this handoff and the passing test
receipt. Reauthenticate original and review inputs before and after computation.
Retain per-row review records, durable logs and terminal completion/failure.

No simulation, reference integration, production change, automatic retry,
polling, regression or follow-up campaign. If accepted, the result closes only
the registered six-control **1 ms CPU pump–leak pilot**, not longer relaxation,
full BETSE parity, biological validation, release promotion or GPU qualification.

The launch acknowledgement is recorded in the living
[progress index](../PROGRESS.md) and [validation index](../validation/betse/README.md).
Do not edit this handoff or registered review code after launch. Return control
after the launch acknowledgement; the user requests subsequent status checks.
