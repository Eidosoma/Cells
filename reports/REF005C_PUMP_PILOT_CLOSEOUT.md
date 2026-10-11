# REF-005c matched pump–leak pilot closeout

2026-09-17, D121. **The refined six-control, 1 ms CPU pilot is independently
closed.** This is numerical correspondence, not equilibrium, biological
validation, complete BETSE parity or a release promotion.

## Result and scope

The D119 capture finished on **2026-09-16 at 18:05:09 UTC**, in **501.812 s**:
616,806 producer comparisons with zero failures, 36 native trajectories,
eighteen observer pairs and twelve exact repeated 6.25 µs records. It reused
24 Cells trajectories, eighteen independent reference solves and six restart
suffixes from the original capture, rather than rerunning them.

The separate D120 review finished at **18:32:49 UTC**, in **337.048 s**. Its
stdlib-only readers and 70-digit reconstruction independently checked:

- **203,274 acceptance comparisons**, with zero failures, plus **10,610,676
  live-law, transfer, conservation and evidence-link comparisons**. These are
  numerical coordinates/checks, not independent biological replicates.
- All **6,720 observed native updates / 20,178 physical records**, including
  interval-start arguments, raw returns, applied density, bath ownership,
  electrical state, sample clocks and native history links.
- **36 refinement groups**, all passing. **23 groups are entirely below their
  registered floors**; they do not establish measured convergence order.
- All eighteen exact observed/unobserved pairs and twelve exact overlap records,
  preserving float64 signed zero. Every producer-reconstructed state/voltage
  coordinate is cross-checked against the independent reconstruction.
- The original 24 Cells NPZ trajectories, six full-state restart suffixes and
  six complete checkpoints, linked to the 213 byte-identical copied files.

The preparation remains seven cells, thirty membrane faces, a single finite
well-mixed **6.75 pL bath**, fixed geometry and maintained ATP/ADP/Pi inputs at
298.15 K. Native FULL INIT uses **6.25 / 3.125 / 1.5625 µs** steps. Cells uses
its ordinary checked RK4 model, `finite_extracellular@2`, with the original
50/25/12.5 µs compiled grids and 50 µs eager comparison. The six controls are
pump+leak, pump-only, leak-only, both blocked, half pump density and a closed
cluster boundary. There are no active channels, junctions, ECM, dynamic
metabolic inventories, water or mechanics in this fixture.

## What resolved the rejection

The original D117 attempt remains rejected. Its finest native timestep was
6.25 µs and missed six energy criteria, as recorded in the
[independent diagnosis](REF005C_PILOT_FAILURE_DIAGNOSIS.md). D119 changed the
native timestep ladder and recording/runtime bounds, not Cells, the physical
parameters, the energy definition or any scientific tolerance.

| Control | Finest native energy-trajectory error (pJ) | Maximum native energy-balance defect (pJ) |
| --- | ---: | ---: |
| Pump + leak | 3.162734e-8 | 7.350781e-8 |
| Pump only | 3.540376e-10 | 1.969189e-9 |
| Leak only | 2.507593e-8 | 5.171267e-8 |
| Both blocked | 0 | 0 |
| Half pump density | 2.828154e-8 | 6.214839e-8 |
| Closed boundary | 3.162665e-8 | 3.512124e-8 |

The energy-balance limit remains **1e-7 pJ**. The trajectory criterion remains
1e-7 pJ absolute plus 1e-5 relative per coordinate; for pump+leak the largest
error/budget ratio is **0.273**. Across the six finest records, maximum amount
and voltage errors are **1.819334e-8 fmol** and **1.510720e-7 V**.

For pump+leak, successive energy-trajectory errors are
1.265548e-7 → 6.326213e-8 → 3.162734e-8 pJ. Measured orders are approximately
**1.00035 and 1.00017**. The energy-balance defect likewise falls from
2.943065e-7 to 7.350781e-8 pJ. This supports first-order native discretization
error as the explanation in this preparation; it is not proof that every
upstream mechanism or every operating regime is correct.

Independent convex chemical/capacitive remainders explain the dominant finite-
step energy defect. They remain diagnostics: **nothing is subtracted to turn a
failed criterion into a pass**. Maximum unexplained remainder over the refined
panel is 1.562466e-10 pJ; this is not a formal floating-point error bound.
Cells does not adopt the source's numerical error or nonce perturbations as
physical behavior.

## Evidence integrity and qualifications

All **641 captured inputs / 55 production modules / 444 sealed capture
payloads**, the four capture terminal/launcher/log files, **eleven audit inputs**
and **22 sealed audit payloads** authenticate. The original failed 431-file
packet, its diagnosis and prior accepted work remain intact. A fresh read-only
identity check on 2026-09-17 confirmed these links; neither simulation nor the
10.61-million-comparison audit was rerun for this document.

The audit's [47 preflight tests](ref-005c-audit-checks-01.xml) passed in 30.06 s.
Stderr contains exactly **72 known disabled-cut notices** in the native capture;
do not describe that capture as warning-free. Native restart pickles are hashed,
not executed, so this is **not native restart qualification**. Per-cell current
and face current identities are checked; unexported smoothing weights are not
independently re-derived.

Native energy is reconstructed independently here. The reused Cells accounting
diagnostics are source-bound saved reports, with the separate
[D114 family accounting review](SPEC010_FAMILY_CLOSEOUT.md) preserved. This
review does not claim a new independent energy reconstruction for every Cells
trajectory. Likewise the adaptive reference trajectories are authenticated and
cross-compared, not reintegrated with arbitrary-precision arithmetic.

## Immutable identities

| Artifact | Directory | Completion SHA-256 |
| --- | --- | --- |
| Refined capture | `runs/ref-005c-refined-pump-2026-09-16/refinement-01` | `45bc4adf9986bf4adc9750af969818b1cf4e0466854e01dbf136e02eb23cba6f` |
| Independent review | `runs/ref-005c-refined-pump-audit-2026-09-16/audit-01` | `e2e67df2b6118cdacfcbf4f23357a972bcb6ecae7d4eacad3f02956ab4369bc1` |

The terminal review status is
`bounded_refined_pump_pilot_independently_closed`. Original producer and handoff
files are not rewritten to retroactively claim independent acceptance.

## Next boundary

The [longer-duration plan](../docs/BETSE_PUMP_RELAXATION_PLAN.md) first qualifies
bounded, lossless recording and matched window/restart behavior, then proposes
a separate **10 ms numerical extension**. Longer relaxation and timed
perturbation need their own convergence/domain and input-semantics gates.
Original biological measurements remain a separate provenance/uncertainty task.

Production remains **0.16.0.dev0**. No full release matrix, solver replacement,
larger timestep, GPU run, tissue/organ qualification or automatic next campaign
is launched by this closeout.
