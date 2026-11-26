<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Integer units at membrane-patch division

At an accepted division, each occupied unit goes to exactly one daughter. The two counts recover the parent in every molecular state, the signed division entries balance, and the two daughters retain the parent's weighted subunit total.

## Assumptions

- State counts are nonnegative integers in declaration order. The draw block covers all occupied units. The mapped daughters are distinct and empty before the parent retires. The first daughter receives units with a binary64 draw strictly below its patch-area share.
- Each state's subunit weight is fixed. The expected sister-count differences additionally assume intact units with independent draws and one common first-daughter probability within each division.

## Lean proof

**Proved**

- [CellsProofs.Tissue.IntegerSegregation.block_mask](../CellsProofs/Tissue/IntegerSegregation.lean#L30)
- [CellsProofs.Tissue.IntegerSegregation.second_membership](../CellsProofs/Tissue/IntegerSegregation.lean#L45)
- [CellsProofs.Tissue.IntegerSegregation.state_counts](../CellsProofs/Tissue/IntegerSegregation.lean#L51)
- [CellsProofs.Tissue.IntegerSegregation.weighted_inventory](../CellsProofs/Tissue/IntegerSegregation.lean#L65)
- [CellsProofs.Tissue.IntegerSegregation.retirement_ledger](../CellsProofs/Tissue/IntegerSegregation.lean#L73)
- [CellsProofs.Tissue.IntegerSegregation.two_unit_difference](../CellsProofs/Tissue/IntegerSegregation.lean#L86)
- [CellsProofs.Tissue.IntegerSegregation.four_unit_difference](../CellsProofs/Tissue/IntegerSegregation.lean#L92)

Direct proof subject `cells.operator.integer_unit_population@1`

Proof sources [Imported Mathlib partition of a finite set by a predicate and its complement](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Finset/Card.lean#L554) · [Imported Mathlib size of a natural half-open interval](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Order/Interval/Finset/Nat.lean#L73) · [Cells specializes its existing independent-trial expectation at two and four units](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/CellsProofs/Chemistry/LineageFission.lean#L106)

## Numerical comparison

**Checked.** On FR-43 development engine 9663f28f, the compiled division matched independently reconstructed counts and signed entries for four parent sites at all six saved times. The weighted daughter pairs were (4, 3), (6, 0), (3, 1) and (0, 0). Volume share, a tie sent to the first daughter and reversed state order gave 3, 1 and 2 incorrect first-daughter entries respectively, while each alternative still conserved total counts. The lead’s registered equal-share run at 52935908 gave 4,058 first-daughter assignments in 8,192 trials and passed its frequency check. [Cells decision D319](https://github.com/Eidosoma/Cells/blob/ac8d915ccefebd31d6357c5ddc0ff4dfc2b39f31/docs/DECISIONS.md#L10061)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.integer_unit_population@1`, `cells.isopotential_partition@1`, `cells.membrane_entity_state@1`

[Division contract at the tested revision](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/docs/library/cells/operators/integer_unit_population%401.md#L103) · [Mask over declared state ranges](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/operators/integer_unit_population.py#L993) · [Retirement and signed site entries](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/operators/integer_unit_population.py#L1006) · [Weighted per-site balance](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/operators/integer_unit_population.py#L1487) · [Entity-axis sum](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/numerics/species_sums.py#L83) · [Parent partition stream](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/numerics/counter_streams.py#L151) · [Lifecycle map at a scheduled division](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/operators/partition.py#L1038) · [Distinct patch and volume shares](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/definitions/partition_spec.py#L97) · [Native composite world and sites](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/validation/fr43_part3/worlds.py#L91) · [Independent counter-stream draws](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/validation/fr43_part3/references/stream_draws.py#L94) · [Declared integer states and weights](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/validation/fr43_part3/references/spec/part3.json) · [Host unit order and exact counts](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/tests/unit/test_integer_unit_population.py#L122) · [Compiled inventory at division](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/tests/unit/test_integer_unit_population_statistics.py#L94) · [Native run and recorded arrays](https://github.com/Eidosoma/Cells/blob/9663f28f36bc9d1595a5bafd08495a805b8dc650/src/cells/records/io.py#L254) · [Proof of counts, books and expected differences](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/CellsProofs/Tissue/IntegerSegregation.lean) · [Parent and daughter counts and plot readings](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/checks/data/coelho_2014_focus_segregation.json) · [Independent-trial expectation](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/CellsProofs/Chemistry/LineageFission.lean#L106) · [Pinned proof dependencies](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/lake-manifest.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/checks/integer_segregation.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8e0fb796849064735e44763cf0322e6fa55b041a/lean/PROGRESS.md#fr43-integer-segregation)

[Tested engine 9663f28f36bc](https://github.com/Eidosoma/Cells/commit/9663f28f36bc9d1595a5bafd08495a805b8dc650) · [Evidence checkpoint 8e0fb7968490](https://github.com/Eidosoma/Cells/commit/8e0fb796849064735e44763cf0322e6fa55b041a)

## Biological evidence

**Open.** Intact units counted in the parent and both daughters at cleavage, with the membrane-patch area inherited by each daughter measured in the same division.

One fission-yeast division preserves the visible focus count. The four-focus cohort split more evenly on average than the independent-allocation expectation for any common daughter probability. These cytoplasmic measurements leave membrane-area-dependent segregation open.

**Unit** visible foci

### coelho2014_movieS3

Hsp104-GFP marks visible cytoplasmic protein aggregates in fission yeast. The parent's one visible focus gives the predicted sum of daughter counts. Upper-left dividing cell, movie labels 120 and 130 min. [Coelho et al. (2014), Movie S3](https://doi.org/10.1371/journal.pbio.1001886.s007)

- **Evidence role** descriptive
- **Evaluation** Visible count before and in both daughters after the same division
- **Observed** 1 visible foci
- **Predicted** 1 visible foci

One image pair. Subthreshold foci and individual protein copy numbers are unresolved.

The larger daughter inherited one visible focus and the smaller daughter inherited zero. This observation supports count conservation in that division. [Dataset manifest](../checks/data/coelho_2014_focus_segregation.json) · [Comparison verdict](../PROGRESS.md#fr43-integer-segregation)

### coelho2014_figure2E

The observable is the mean absolute difference between the sisters' focus counts. For four intact units with independent allocation, 1.5 is the smallest expected difference over all common daughter probabilities. For two units the minimum is 1. Green experimental series, groups with two and four visible foci at division. [Coelho et al. (2014), Figure 2E](https://doi.org/10.1371/journal.pbio.1001886.g002)

- **Evidence role** descriptive
- **Evaluation** Two foci at division, 33 divisions, Four foci at division, 32 divisions, reported below
- **Observed** 1 visible foci
- **Predicted** 1.5 visible foci

Mean differences and SEMs are approximate readings from the plot. The SEM is about 0.18 visible foci in each group. Membrane area fractions paired with these counts were unavailable.

Two foci gave about 0.97 against the equal-share expectation of 1. Four gave about 1.0 against the minimum expectation of 1.5. Aggregate fusion and spatial confinement limit transfer of this comparison to membrane units. [Dataset manifest](../checks/data/coelho_2014_focus_segregation.json) · [Comparison verdict](../PROGRESS.md#fr43-integer-segregation)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
