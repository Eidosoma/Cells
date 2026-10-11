# REF-004a independent saved-channel closeout

D088, 2026-09-13. The user reviewed the 11.971-second channel capture and
requested its independent audit. This document specifies that audit, not an
automatic channel-plus-cell run. The original capture/design/source, all three
software receipts and the prelaunch handoff remain immutable.

## Frozen evidence and exact scope

Input: `runs/ref-004a-kv1p5-2026-09-13/capture-01`. Its pending completion hash is
`6e694ba8d91eec64b7bfde33b1e099047952724c25c90b0f3ba520f1265ca190`.
The separately recorded registration and comparison hashes are bound in the
audit source. Authenticate all 13 files, exact nine-payload membership, the
11-input source capsule, original 63-test receipt, prior D086 receipt/payloads,
352 accepted implementation files and all 332 installed BETSE Python files.
Check runtime/lock/source provenance, clocks, CPU/float64/backend identity,
temperature restriction, explicit m/h preparation and derived initial P.

The capture includes six isolated voltage protocols, 18 runs per engine and
1/0.5/0.25 ms steps. Static kinetics/one-step probes use NumPy/eager/JIT;
complete Cells histories use compiled JAX only. Preserve all 36 measured
refinement ratios and 12 roundoff-limited diagnostics. No coupled membrane,
ionic flow, whole-cell clamp, channel-target pathway, biological calibration,
GPU, arbitrary waveform convergence or full channel-family parity is implied.

## Separate numerical reconstruction

First replay all **11,266 original comparisons exactly** with the unchanged
captured checker. Then use a separately written, model-free 80-digit Decimal
implementation to rebuild all 11,266 rows, their identities, expectations,
errors, verdicts and aggregate diagnostics:

- Independent SI logistic expressions use `exp(x)/(1+exp(x))`; native source
  mV/ms conversion is not reused as executable reference code.
- For each held segment, obtain an affine update from two basis states. Native
  uses its implicit one-step equation; RK4 uses four explicitly computed
  derivative stages, not the original fourth-degree polynomial.
- Compose those affine maps by binary exponentiation to the observation time.
  This is high-precision reference arithmetic, not a BETSE/Cells trajectory run.
- Reconstruct continuous histories from event anchors using exponentials, with
  separately assembled integer clocks and right-continuous voltage events.
- Check both gates, open-product readouts, initial states, all protocol/backend/
  timestep coverage, finest continuous errors, error ratios, hidden-state
  separation and direct engine differences. Preserve the six explicit hidden-
  history checks in addition to the original counted rows.

The eight original check groups contain 208 / 26 / 78 / 5952 / 1984 / 2976 /
36 / 6 comparisons (kinetics, equilibrium init, one RK4 step, discrete gates,
continuous gates, open fraction, measured refinement and equal initial opening).
Every independently reconstructed binary64 row must match the saved record;
no physical tolerance, condition or failed diagnostic is loosened or removed.
Roundoff-limited reports are not observed-order passes.

An import fence rejects Cells, BETSE, NumPy, JAX/jaxlib and SciPy. Both source
packages and old capture files are read only. The audit cannot independently
recover unrecorded intermediate runtime arrays: all-stage validity is supported
by the recorded worker flags and authenticated checked-step source, not a claim
that actual intermediate state arrays were saved. No engine is imported or rerun.

## Short verification and result

Run focused actual-packet/corruption tests alongside the unchanged 63 original
adapter tests. The final receipt binds exact previous test identities and all
new audit-test identities, with no failures/errors/skips. Temporary corrupted
copies do not overwrite source evidence. No whole-production regression job.

The short combined preflight now passes **102 tests in 2.58 s**: all 63 unchanged
adapter tests and 39 new audit/evidence checks. The receipt is
`reports/ref-004a-audit-checks-01.xml`. The independent 80-digit calculation
reproduces every saved comparison exactly; no original numerical criterion or
source required a correction. This software receipt is separate from the new
actual closeout receipt at
`runs/ref-004a-kv1p5-audit-2026-09-13/audit-01/completion.json`.

One read-only closeout attempt then writes a new directory under `runs`, never
inside the original packet. It records its inputs, source capsule, independent
comparison table and completion/failure receipt. Limit this small audit to
**30 seconds / 16 MiB new artifacts**, CPUs 0–3. A result is established only
by its new actual completion receipt. No automatic retry or subsequent run.
If a future audit/regression needs a longer budget, use the detached/no-poll
policy rather than extending this attempt silently.

Only a pass can set `isolated_gate_qualified: true`. The original pending
capture is not rewritten. After closeout, the next work is the separately
specified [coupled-channel design](BETSE_COUPLED_CHANNEL_PLAN.md), initially
source/configuration and instantaneous transport alignment, not a large run.
