<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A size-triggered division preserves each membrane species across both daughter records

Ranking the occupied membrane places gives a daughter of size k and a sibling of size N − k. When 0 < k < N, each daughter starts below the parent’s threshold. Their per-species counts sum to the parent’s.

## Assumptions

- One membrane molecule occupies each ranked place. A join reaches the trigger at N, the partition selects the first k places, and the sibling receives the complement.
- k is the integer obtained by flooring the engine’s binary64 product of the configured fraction and N. The proof takes the realized rank, including a stable ordering of tied uniforms, and the proper integer quota as inputs.
- The first daughter continues and the second goes to the discard sink. The claim covers the membrane species array. Held pools have their own accounting.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.LineageFission.ranked_division](../CellsProofs/Chemistry/LineageFission.lean#L50)
- [CellsProofs.Chemistry.LineageFission.ranked_sizes](../CellsProofs/Chemistry/LineageFission.lean#L23)
- [CellsProofs.Chemistry.LineageFission.binary_inventory](../CellsProofs/Chemistry/LineageFission.lean#L42)

Direct proof subject `cells.operator.size_threshold_division@1`

Proof sources [Cells reuses the existing ranked quota and per-species inventory](../CellsProofs/Chemistry/LineageFission.lean#L23) · [Imported Mathlib cardinality of the complementary set](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Fintype/Card.lean#L130)

Uses [Size-triggered fission conserves each species under fixed-quota and independent partitions](size-threshold-fission.md)

## Numerical comparison

**Checked.** All 30 divisions in 300 exact events matched the independent trace and rank reconstruction. At threshold 15, the two daughters kept 6 and 9 membrane molecules. All three species, every continued-daughter row and 89 discard transfers matched. Two tied-rank controls selected the expected species at the boundary.

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.ideal_mixing@1`, `cells.transition_state_factor@1`

**Operators** `cells.size_threshold_division@1`

[Division trigger and continuation](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/models/assembly_lineages_v2/size_division.py#L325) · [Realized integer quota and ranked molecule places](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/models/assembly_lineages_v2/size_division.py#L246) · [Parent and both daughter compositions](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/models/assembly_lineages_v2/size_division.py#L296) · [Saved fission table](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/models/assembly_lineages_v2/size_division.py#L373) · [Per-species sink transfers](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/models/assembly_lineages_v2/records.py#L825) · [Schema and writer for saved relations](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/records/relations.py) · [Three-species exact-event fixture](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/tests/unit/test_assembly_lineages_v2_size_division.py#L64) · [Ranked split and complementary inventories](https://github.com/Eidosoma/Cells/blob/6f52662bb897014f8c0f9470e9ef95cb5a0fb142/lean/CellsProofs/Chemistry/LineageFission.lean) · [Counts of marked places in a daughter](https://github.com/Eidosoma/Cells/blob/6f52662bb897014f8c0f9470e9ef95cb5a0fb142/lean/CellsProofs/Chemistry/VesiclePopulation.lean) · [Pinned Mathlib dependency](https://github.com/Eidosoma/Cells/blob/6f52662bb897014f8c0f9470e9ef95cb5a0fb142/lean/lake-manifest.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6f52662bb897014f8c0f9470e9ef95cb5a0fb142/lean/checks/size_threshold_division.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6f52662bb897014f8c0f9470e9ef95cb5a0fb142/lean/PROGRESS.md#size-threshold-division)

[Tested engine 2263d11ce509](https://github.com/Eidosoma/Cells/commit/2263d11ce5099fca1e58b9285ff4d302bb829fdf) · [Evidence checkpoint 6f52662bb897](https://github.com/Eidosoma/Cells/commit/6f52662bb897014f8c0f9470e9ef95cb5a0fb142)

## Biological evidence

**Open.** Parent and paired daughter membrane counts by species at an independently observed growth threshold.

**Unit** dimensionless diameter ratio for the geometric comparison

### deshpande2018_daughter_diameters@1

Mechanically divided liposomes at a microfluidic Y-junction. Each pair contributes the smaller daughter diameter divided by the larger. Figure 3a and its accompanying text, 152 pairs. Figure 4a from the same paper supplies the separate lumen-dye comparison under vesicle shear fission. [Deshpande et al. (2018), Fig. 3a](https://doi.org/10.1021/acsnano.7b08411)

- **Evidence role** descriptive
- **Observed** 0.97 dimensionless diameter ratio for the geometric comparison

The paper reports 0.03 as the standard deviation of the diameter ratio across pairs.

The diameters describe approximate geometric symmetry. The size-triggered operator specifies molecule counts. The experiment leaves the growth threshold and membrane inventory of each daughter unmeasured. [Dataset manifest](../checks/data/vesicle_population_measurements.json) · [Comparison verdict](../PROGRESS.md#size-threshold-division)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
