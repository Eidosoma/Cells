<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Neutral label fluxes add and labels can exchange across a face with zero parent flux

For any finite partition of a neutral tracer, the sum of its label fluxes equals the parent flux under a common linear diffusion coefficient. With opposing 90:10 label fractions, a charged Cells face at fixed nonzero voltage instead gives a row sum (8/5)/ln(9) times the unsplit flux.

## Assumptions

- Labels partition the material, share transport coefficients and experience the same voltage. Concentrations at both ends of each active logarithmic-mean face are positive and RT is positive.
- The ideal Fick and neutral constant-field statements are exact over the reals. On the Cells face the exact neutral reduction uses equal concentrations or |(a−b)/(a+b)| ≥ 10⁻⁴ on every label and the parent. The small nonzero-gradient polynomial has a compiled comparison.
- The charged example holds voltage fixed and changes only the representation of the tracer. Its ratio applies when the unsplit flux is nonzero.

## Lean proof

**Proved**

- [CellsProofs.Transport.LabelDiffusion.fick_sum](../CellsProofs/Transport/LabelDiffusion.lean#L20)
- [CellsProofs.Transport.LabelDiffusion.opposing_labels](../CellsProofs/Transport/LabelDiffusion.lean#L26)
- [CellsProofs.Transport.LabelDiffusion.neutral_permeation_sum](../CellsProofs/Transport/LabelDiffusion.lean#L32)
- [CellsProofs.Transport.LabelDiffusion.neutral_face_eq_fick](../CellsProofs/Transport/LabelDiffusion.lean#L56)
- [CellsProofs.Transport.LabelDiffusion.neutral_face_sum](../CellsProofs/Transport/LabelDiffusion.lean#L75)
- [CellsProofs.Transport.LabelDiffusion.charged_opposing_ratio](../CellsProofs/Transport/LabelDiffusion.lean#L88)
- [CellsProofs.Transport.LabelDiffusion.charged_ratio_bounds](../CellsProofs/Transport/LabelDiffusion.lean#L101)

Direct proof subject `cells.route.logmean_electrodiffusion@1`, `cells.route.passive_neutral_permeation@1`

Proof sources [Mathlib finite-sum distributivity, imported for common Fick mobility](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Ring/Finset.lean#L50-L52) · [Mathlib lower bound for log(1+x), specialized to x = 8](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Deriv.lean#L333-L337) · [Cells logarithmic-mean face, specialized to separate label rows](../CellsProofs/Transport/LogMeanFace.lean)

Uses [Extracellular face flux follows the electrochemical potential drop](extracellular-face-direction.md) · [Passive neutral solute follows its concentration gradient](neutral-permeation.md)

## Numerical comparison

**Checked.** Both nodes’ explicit labels summed to the parent at all 101 times. The right label reached 0.299998884 fmol at 1 s against 0.3 analytically. The compiled +1, +10 mV face gave a split-to-parent flux ratio of 0.7281913813014701.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `logmean_electrodiffusion@1`

[Face flux and electric driving force](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/src/cells/numerics/surface_transport.py#L281-L296) · [Logarithmic mean and series threshold](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/src/cells/numerics/extracellular_field.py) · [Implicit face weights](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/src/cells/numerics/surface_imex.py#L109-L135) · [Two finite nodes and explicit label rows](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/validation/regions/example.py#L73-L102) · [Per-node history and amount reconstruction](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/validation/regions/readouts.py#L269-L315) · [Surface component inputs](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/validation/tissue/surface_fixtures.py) · [Regression for exchange hidden in net records](https://github.com/Eidosoma/Cells/blob/1295a7d794feb508bdf565ca2244aff3380b27d6/tests/unit/test_region_readouts.py#L138-L152) · [Label proofs](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/CellsProofs/Transport/LabelDiffusion.lean) · [Cells face law](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/CellsProofs/Transport/LogMeanFace.lean) · [Neutral permeation proof](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/CellsProofs/Transport/NeutralPermeation.lean) · [Imaging measurement record](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/checks/data/regional_tracer_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/checks/label_diffusion.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/PROGRESS.md#fr33-label-diffusion)

[Tested engine 1295a7d794fe](https://github.com/Eidosoma/Cells/commit/1295a7d794feb508bdf565ca2244aff3380b27d6) · [Evidence checkpoint 9a39ed6f20c9](https://github.com/Eidosoma/Cells/commit/9a39ed6f20c95e17809b594a9800a41633d8c552)

## Biological evidence

**Open.** Redistribution of a labelled molecular species, with matched diffusion coefficients and independently measured parent and label fluxes.

**Unit** Relative fluorescence in the experiment and fmol in the simulation

### gray2006_psd95_exchange

Photoactivated PSD-95 in one dendritic spine fell while green fluorescence increased in two nearby spines. Figure 4A. [Gray et al. (2006), PLOS Biology](https://doi.org/10.1371/journal.pbio.0040370)

- **Evidence role** descriptive

Green fluorescence was normalized to red fluorescence. The panel supplies no calibrated amount or common diffusion coefficient for the label and its complement.

Label redistribution is observed. Equal mobility, the parent flux and the charged-face ratio remain unmeasured in this preparation. [Dataset manifest](../checks/data/regional_tracer_measurements.json) · [Comparison verdict](../PROGRESS.md#fr33-label-diffusion)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
