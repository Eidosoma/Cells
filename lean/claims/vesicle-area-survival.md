<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Vesicle area variation bounds survival during a tension hold

Under a common hazard per unit area, survival evaluated at the initial mean area bounds the cohort’s survival from below. The linear interpolation of the two endpoint survivals at that mean bounds it from above. An endpoint mixture attains the upper bound.

## Assumptions

- Every vesicle has fixed area during observation, the same integrated hazard per unit area and single-vesicle survival exp(−qA). The initial finite cohort weights are nonnegative and sum to one.
- For the upper bound, L and U are actual limits on the same initial cohort’s areas and L < U. If L = U the common single-area result is exact. Positive exposure and unequal areas with positive weights give a strict lower bound.
- For spherical vesicles the required mean area is 4π times the mean of squared radii. Inferring area from a mean radius alone requires further information. D293’s set-2 allowance addresses area differences across preparations. The bound here concerns the survival curve within one cohort.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleArea.at_mean_le](../CellsProofs/Chemistry/VesicleArea.lean#L18)
- [CellsProofs.Chemistry.VesicleArea.at_mean_lt](../CellsProofs/Chemistry/VesicleArea.lean#L26)
- [CellsProofs.Chemistry.VesicleArea.endpoint_mixture](../CellsProofs/Chemistry/VesicleArea.lean#L42)
- [CellsProofs.Chemistry.VesicleArea.le_chord](../CellsProofs/Chemistry/VesicleArea.lean#L54)
- [CellsProofs.Chemistry.VesicleArea.population_le_chord](../CellsProofs/Chemistry/VesicleArea.lean#L68)
- [CellsProofs.Chemistry.VesicleArea.one_area](../CellsProofs/Chemistry/VesicleArea.lean#L80)

Proof sources [Mathlib exponential convexity and strict convexity, imported for survival](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/SpecificFunctions/Basic.lean#L37-L60) · [Mathlib finite Jensen inequality and its strict form, specialized to initial cohort weights](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Jensen.lean#L63-L100) · [D293 records a separate area allowance across preparations for the registered blind test](https://github.com/Eidosoma/Cells/blob/562cc9b4ec5225089feee26cab3ad2ef42405e02/docs/DECISIONS.md#d293-the-rupture-blind-tests-stage-1-rulings-made-before-any-prediction-or-held-out-value) · [Cells tagged FR-31 law sheet, area scaling and survival](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock)

## Numerical comparison

**Open.** Four synthetic calculations passed. With mean area 2 and range 1 to 3, the lower and upper bounds are 1/4 and 5/16 at the selected exposure. Two cohorts give 5/16 and 9/32. Equal areas and zero exposure give equality. An FR-31 engine comparison is pending.

**Reference calculation**

[Declared area scaling and fixed-tension survival](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock) · [Finite-cohort survival bound and endpoint construction](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/vesicle_area.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr31-area-bounds)

[Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

## Biological evidence

**Open.** Initial vesicle areas from the same at-risk population, held tension, and time to first rupture or censoring per vesicle. Linked observations would quantify the mean-area approximation.

**Unit** Surviving fraction at a stated exposure

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
