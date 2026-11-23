<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A finite error bound for survival after an RNA release window

For a positive measured count at window close, a proposed survival fraction can be checked against the two counts. The change in the later count contributes its absolute error and the uncertainty in the close count contributes that error times the proposed fraction.

## Assumptions

- The same cohort is followed through the chase, with common nonnegative survival factors and no new members. Their product is the expected ratio.
- Both count uncertainties bound absolute errors in the same amount unit. The engine estimates these from a coarser grid. A missing estimate leaves the numerical comparison unresolved, and an empty cohort has no survival ratio.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalWindow.count_residual_le](../CellsProofs/Chemistry/ArrivalWindow.lean#L77)
- [CellsProofs.Chemistry.ArrivalWindow.ratio_residual_iff](../CellsProofs/Chemistry/ArrivalWindow.lean#L92)
- [CellsProofs.Chemistry.ArrivalWindow.chase_ratio_error](../CellsProofs/Chemistry/ArrivalWindow.lean#L100)

Direct proof subject `cells.templated_polymerisation@1`

Proof sources [Mathlib triangle inequality specialized to the two count errors](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Group/Abs.lean#L73-L78) · [Mathlib absolute value of a quotient](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Field/Basic.lean#L648-L652) · [Mathlib nonnegative product of chase factors](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/BigOperators/Ring/Finset.lean#L30-L34) · [Cells count and ratio definitions](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/cohort.py#L200-L216)

Uses [Marked RNA is accounted for in both release fates, including after label reuse](release-window-survival.md)

## Numerical comparison

**Checked.** The repaired checker gave the expected four control verdicts. Three samples yielded insufficient resolution, a resolved ratio of 1 failed against ¼, an empty cohort was identified, and the turnover control passed. All eight R1/R2 ratios reread from compiled exports passed with finite estimated error. The previous checker gave a false pass and raised on the empty cohort. These eight development readouts use the original exports. The independent registered FR-38 comparison subsequently failed R1 and found R2 inconclusive.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Public window counts and estimated discretization error](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/cohort.py#L142-L218) · [Saved release counters and local row resolution](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/cohort.py#L255-L320) · [R1/R2 half-lives](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/sheet_check.py#L955-L962) · [R1 development world](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/worlds.py#L519-L558) · [Per-fate export](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/engine_run.py#L393-L416) · [Operator producing the cumulative release counters](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/operators/templated_polymerisation.py) · [Repaired public verdict and its two refusal reasons](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/gene_regulation/release_check.py#L329-L358) · [Four checker regression cases](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/tests/unit/test_gene_regulation_compare.py#L377-L422) · [Cohort identity and error propagation](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/release_survival.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/PROGRESS.md#fr38-survival-readout)

[Tested engine 57c3cb909db5](https://github.com/Eidosoma/Cells/commit/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b) · [Evidence checkpoint cecbe3627a7a](https://github.com/Eidosoma/Cells/commit/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Public window counts and estimated discretization error](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/cohort.py#L142-L218) · [Saved release counters and local row resolution](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/cohort.py#L255-L320) · [Verdict before the repair](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/release_check.py#L329-L349) · [R1/R2 half-lives](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/sheet_check.py#L955-L962) · [R1 development world](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/worlds.py#L519-L558) · [Per-fate export](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/validation/gene_regulation/engine_run.py#L393-L416) · [Operator producing the cumulative release counters](https://github.com/Eidosoma/Cells/blob/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a/src/cells/operators/templated_polymerisation.py) · [Cohort identity and error propagation](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/release_survival.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/PROGRESS.md#fr38-survival-readout)

[Tested engine ce0ce9b26492](https://github.com/Eidosoma/Cells/commit/ce0ce9b26492e7b4b7e4170104294b7338fb9e1a) · [Evidence checkpoint cecbe3627a7a](https://github.com/Eidosoma/Cells/commit/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78)

## Biological evidence

**Open.** The same release-marked molecules counted at the end of the window and again after the chase, with uncertainties on both counts.

**Unit** Surviving fraction (0–1)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
