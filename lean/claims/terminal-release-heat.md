<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# RNA detachment books its free-energy drop once

Each physical release fate books nonnegative heat throughout the active domain. An inactive fate books zero even while its amount changes through degradation. With concurrent synthesis, release and degradation, the sum of the three heats cancels the total free-energy change.

## Assumptions

- At fixed temperature and volume, fate and held RNA share a standard energy per molecule at 1 M. Both endpoints of an active fate are positive and at or below the domain limit.
- The finite-step chemical potential is the divided difference of the row’s ideal free energy. At equal amounts it is the derivative. Each nonnegative detachment uses its physical fate’s potential. The durable fraction may be anywhere in [0,1].
- The same signed extents change the hold, the receiving and degraded rows and the corresponding heat classes. The fixed-temperature balance here has no external work.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ReleaseEnergy.ideal_antitone](../CellsProofs/Chemistry/ReleaseEnergy.lean#L28)
- [CellsProofs.Chemistry.ReleaseEnergy.slope_change](../CellsProofs/Chemistry/ReleaseEnergy.lean#L36)
- [CellsProofs.Chemistry.ReleaseEnergy.slope_nonpos](../CellsProofs/Chemistry/ReleaseEnergy.lean#L44)
- [CellsProofs.Chemistry.ReleaseEnergy.heat_nonneg](../CellsProofs/Chemistry/ReleaseEnergy.lean#L61)
- [CellsProofs.Chemistry.ReleaseEnergy.zero_release](../CellsProofs/Chemistry/ReleaseEnergy.lean#L66)
- [CellsProofs.Chemistry.ReleaseEnergy.split_heat_nonneg](../CellsProofs/Chemistry/ReleaseEnergy.lean#L68)
- [CellsProofs.Chemistry.ReleaseEnergy.booking_balance](../CellsProofs/Chemistry/ReleaseEnergy.lean#L78)

Direct proof subject `cells.operator.templated_polymerisation@1`

Proof sources [Mathlib derivative of x log x, imported and specialized to the ideal row](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/NegMulLog.lean#L51-L60) · [Mathlib derivative sign on a convex interval](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L474-L490) · [Cells completion and per-fate heat](https://github.com/Eidosoma/Cells/blob/e924f450ad74a878eda6727ac255527ec5d74ff7/src/cells/operators/templated_polymerisation.py#L1355-L1400)

## Numerical comparison

**Checked.** The maximum isolated heat discrepancy was 4.36 × 10⁻²² pJ over 18 compiled rows. Under synthesis and degradation the largest full balance error across 60 half-steps was 3.83 × 10⁻¹⁹ pJ. Forty inactive fate half-steps had ongoing loss and exactly zero release heat. Equal release and loss in a separate component move booked positive heat at unchanged amount.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Engine divided potentials and each route’s finite-step heat](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/operators/templated_polymerisation.py#L1342-L1400) · [Accepted half-step updates and cumulative energy counters](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/operators/templated_polymerisation.py#L1403-L1513) · [Windowed execution and observation grid](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/execution/windows.py) · [Compiled collection and export](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/validation/gene_regulation/engine_run.py#L169-L181) · [R1 fixtures and standard state](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/validation/gene_regulation/worlds.py#L519-L558) · [Half-step kernel and control extraction](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/validation/gene_regulation/kernel.py#L39-L87) · [Thermal and amount units](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/validation/gene_regulation/sheet_check.py#L87-L97) · [Exact sign and finite-step balance](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/CellsProofs/Chemistry/ReleaseEnergy.lean) · [Shared compiled-trajectory collector](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/checks/terminal_release.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/checks/release_energy.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/PROGRESS.md#fr38-release-energy)

[Tested engine fe6d25e9eee7](https://github.com/Eidosoma/Cells/commit/fe6d25e9eee7a7d0422568fd356a57e67ef03301) · [Evidence checkpoint b475c62fbfbc](https://github.com/Eidosoma/Cells/commit/b475c62fbfbcb913f12498b71681e8cbf057d433)

## Biological evidence

**Open.** An independently constrained chemical-potential drop per detached RNA in a defined physical fate at measured activities and temperature. The available RNA release curves measure timing and amounts.

**Unit** pJ per fmol detached

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
