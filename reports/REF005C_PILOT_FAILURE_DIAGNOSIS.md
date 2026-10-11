# REF-005c failed-pilot diagnosis

2026-09-16, D118. **Rejection independently reproduced and explained; the pilot
remains unqualified.** No simulator/reference rerun, production edit, upstream
edit, acceptance-budget change or replacement capture is performed here.
The [original contract](../docs/BETSE_MATCHED_PUMP_PILOT.md) and
[handoff](REF005C_MATCHED_PUMP_HANDOFF.md) remain immutable.

## What completed, and what failed

The detached pilot stopped after **385.829 s** in its final comparator. Earlier
phases completed: 48 held states / three backends / 12,960 mapping comparisons,
18 independent reference solves, 36 native runs / 18 observer pairs, 24 Cells
trajectories and six restart suffixes. The first blocking check was
`native_finest_energy`, so the original fail-fast comparator did not inventory
all later criteria. Completing the calculations was not a qualification pass.

The separate saved-data diagnosis completed in **41.424 s**. It independently
evaluates **203,274 registered-budget comparisons**, finding exactly **six
failed scalar comparisons in six groups**. All **36 refinement groups** pass;
floor-limited groups are not evidence of measured convergence order.

At the finest native step, **6.25 µs**:

| Control | Largest energy-trajectory error (pJ) | Budget at worst coordinate (pJ) | Maximum energy-balance defect (pJ) |
| --- | --- | --- | --- |
| Pump + leak | 1.26555e-7 — fail | 1.16004e-7 | 2.94307e-7 — fail |
| Pump only | 1.41615e-9 | 1.03926e-7 | 8.48573e-9 |
| Leak only | 1.00339e-7 | 1.12121e-7 | 2.06923e-7 — fail |
| Both blocked | 0 | 1.00000e-7 | 0 |
| Half pump density | 1.13166e-7 | 1.14063e-7 | 2.48631e-7 — fail |
| Closed boundary | 1.26552e-7 — fail | 1.16004e-7 | 1.40659e-7 — fail |

The energy-balance budget is **1e-7 pJ absolute**. The trajectory budget includes
the original relative term; an error slightly above 1e-7 pJ does not necessarily
fail. Both trajectory misses occur at **1 ms, cell index 6** (the seventh cell).
The first is **1.09096 times its budget**, approximately 9.1% over the limit.

Finest native amount/voltage and cross-engine comparisons pass. Across all
three compiled Cells grids, maximum reference differences are **8.671e-16 fmol,
1.744e-15 pJ and 7.317e-15 V**. These are differences against the saved numerical
reference in this short fixture, not biological accuracy or an exact-solution
guarantee. Eager/compiled agreement and the reported Cells accounting limits pass.

## Why the mismatch occurs

The pinned native driver accumulates pump and passive fluxes at the interval
start, then updates concentrations explicitly using `dt * flux`. See
[`sim.py`](../upstream/betse-v1.5.0/betse/science/sim.py) and
[`update_Co`](../upstream/betse-v1.5.0/betse/science/sim_toolbox.py).
Our native energy bookkeeping integrates those actual held interval fluxes;
it does not replace them with later recomputed fluxes or the sodium-rate diagnostic.

For pump+leak, maximum energy-trajectory errors at **25 / 12.5 / 6.25 µs** are
**5.06950e-7 / 2.53231e-7 / 1.26555e-7 pJ**: approximately a factor of two
improvement on each halving. Measured orders are 1.00139 and 1.00069. Other active
controls show the same first-order energy pattern.

An independent 70-digit calculation uses **total applied ionic transfer** and
the **potassium pump return / 2**, rather than the producer's passive-flux plus
sodium-return decomposition. It reconstructs chemical energy, capacitance
energy, maintained chemical work and signed dissipated energy from saved data.
For a finite explicit step, the leftover energy consists of the convex
first-order Taylor remainder, plus floating-point update residuals:

```text
energy change + integrated dissipation - maintained work
  = chemical Taylor remainder + ½ C (voltage change)² + roundoff remainder
```

The chemical term is `RT × [n_new ln(n_new/n_old) − (n_new − n_old)]`, summed
over cells and the shared bath with explicit unit conversion. It is nonnegative,
as is the capacitive term. These are diagnostic terms, **not subtractions used
to repair the saved dissipation or waive acceptance criteria**.

For finest-step pump+leak, the accumulated capacitive remainder is
**2.94243e-7 pJ**, the chemical remainder **5.09451e-11 pJ**, and the final
unexplained remainder **1.29993e-11 pJ**. Together the convex terms account for
**99.9956%** of the observed balance defect. Across all eighteen native
trajectories the largest unexplained accumulated remainder is **5.165e-11 pJ**.
This agrees with the small saved concentration-update rounding residuals; it
is not a formal floating-point error proof.

Thus the evidence supports **native first-order time discretization and its
left-endpoint energy quadrature**, rather than a missing factor of three, wrong
sign, bath ownership error or Cells-model correction. This diagnosis is specific
to this source-compatible preparation and bookkeeping, not a blanket claim
about every BETSE model or integrator.

## Evidence strength and limits

- All **629 original inputs / 55 production modules** authenticate against the
  original registration and source archive. All **431 failed-attempt files**
  (418,363,630 bytes) are sealed at review start and rechecked unchanged at end.
  This is a new preservation manifest, **not an invented original completion
  manifest**: the failed producer had no successful completion receipt.
- **376,320 additional flux/transfer comparisons** pass across **1,680 observed
  native updates**. Applied density, -3/+2 stoichiometry, boundaries, live
  chronology, positive chemistry and single owned cell/bath transfers are
  checked. Largest single-bath rounding residual: 4.326e-13 fmol.
- All eighteen native observer pairs match. Exported native array-byte hashes
  verify. All 24 Cells observation records are linked directly to independently
  decoded NPZ arrays. Six full-state restart suffixes are byte-compared as
  float64 values, including signed zero; six complete checkpoint state/layout
  links verify without executing a simulator or loading native pickles.
- Reference aggregate/individual records and all three-method-setting agreement
  comparisons are checked from saved numbers. This does not rerun or certify
  an exact ODE solution. Cells accounting limits here use source-bound saved
  diagnostics; native energy accounting is independently reconstructed.
- Simulator, array-runtime, independent ODE-reference and producer-helper
  imports are fenced. **33 diagnosis tests pass in 1.73 s**, including chemical
  and capacitive identities, corrupted evidence, signed-zero distinction,
  import fencing and actual saved Cells/checkpoint decoding.

Software receipt 01 retains the first 32-check scope. Receipt 02 retains a
diagnostic-reader failure when its new checkpoint test exposed the existing
`cell_ids` trajectory / `ids` complete-layout naming difference. The controller
refused that nonpassing receipt before creating a review attempt. The reader
now maps those documented representations explicitly, without changing the
production archives or weakening identity checks; receipt 03 binds the final
33-check source used for this diagnosis.

Original registration SHA-256:
`2dc09a3d112b1f0efc3a03d0a43f9cc2a395078553881ba7a7cc33497dff269b`.
Original failure SHA-256:
`b6e2624a2dc39dd5204bc7a660d608944079d615ac7c564c9c5ea56581d72500`.
Diagnosis: `runs/ref-005c-pilot-diagnosis-2026-09-16/review-01`.
Completion SHA-256:
`c6b5f18258d1fa14c2e742fa76b582c0bc7c32ff9e729d96800d8475830a8bb3`.

## Recommended next slice — not launched

Prepare a separately registered **6.25 / 3.125 / 1.5625 µs native ladder**, retaining
all six controls and observed/unobserved partners. Repeat 6.25 µs as an exact
overlap control; reuse the preserved Cells trajectories and independent references
if their identities and comparison definitions remain unchanged. No physical
parameter, duration, energy definition or scientific tolerance should change.

One further halving is probably insufficient: the measured pump+leak balance
defect predicts about **1.47e-7 pJ at 3.125 µs** and **7.36e-8 pJ at 1.5625 µs**.
These are extrapolations to plan an experiment, **not passing results**.

Register revised recording/runtime bounds first. The current 160-step observed
result is 35,860,564 bytes; a 640-step result will likely exceed the old 64 MiB
per-file limit. An explicit larger allowance or separately verified chunked
recording is needed. Do not discard raw evidence or silently exceed old caps.

Only after that separately authorized detached capture and independent review
could this short matched scope close. Longer relaxation, experiments, additional
transporters, spatial composition, GPU qualification and organ-scale validation
remain distinct. The engineering lesson is to keep mechanism, integration error
and discrete energy bookkeeping separately inspectable across resolutions.
