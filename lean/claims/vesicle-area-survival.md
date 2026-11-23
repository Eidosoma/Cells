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

**Checked.** Four synthetic checks cover distinct and identical areas and zero exposure. At one second, two equally weighted founders in the compiled shared-pool runner give 0.3577327717421851 from their recorded hazards. The mean-area lower bound is 0.3561630590540235 and the upper chord is 0.3577327717421859. The calculation uses rate-implied probabilities.

**Reference calculation**

[Declared area scaling and fixed-tension survival](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock) · [Finite-cohort survival bound and endpoint construction](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/vesicle_area.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr31-area-bounds)

[Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

**Engine** `cells.assembly_lineages@2`, `cells.pore_nucleation@1`

**Operators** `cells.tension_hold@1`

[Pore rate and temperature slope](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_nucleation.py#L58) · [Tension domain and hold payer](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/tension_hold.py#L88) · [Clock, opening and release](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_clock.py#L82) · [Single-lineage pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/runner.py#L363) · [Population pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/population.py#L665) · [Per-founder random stream and threshold inputs](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/streams.py) · [Geometry and area in both runners](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/geometry.py) · [Closed-form work oracle, founder worlds and both public run modes](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/unit/test_assembly_lineages_v2_pores.py) · [Base assembly run definition](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/assembly_lineage_v2_fixtures.py) · [Exact rate, heat and recorded cutoff proof](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesiclePore.lean) · [Common-exposure survival bounds](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Measured pore observables](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/data/dopc_pore_observables.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/vesicle_pore.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/PROGRESS.md#fr31-pore-endpoint-repair)

[Tested engine 0a1c1b0dc814](https://github.com/Eidosoma/Cells/commit/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe) · [Evidence checkpoint 1c3c422d32a6](https://github.com/Eidosoma/Cells/commit/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87)

## Biological evidence

**Open.** Initial vesicle areas from the same at-risk population, held tension, and time to first rupture or censoring per vesicle. Linked observations would quantify the mean-area approximation.

**Unit** Surviving fraction at a stated exposure

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
