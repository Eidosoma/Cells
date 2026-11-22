<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A reused release-time label carries forward its older survivors

Half-open arrival windows assign releases at a shared boundary exactly once. In a well-mixed pool with common survival factors, the surviving amount after label reuse is the sum of the two separately followed release histories. The chase fraction uses the original cohort alive at window close.

## Assumptions

- Time is indexed by step boundaries. In the exact event example a molecule is marked on detachment and experiences the following interval’s survival factor. Sampling is before any new releases at that sample boundary.
- Every member of the same physical pool experiences the same survival factor in each interval. For a physical chase each factor is in [0,1]. A reused label receives new material from nonoverlapping windows.
- A zero denominator gives an undefined chase fraction. A host readout with only interval totals assumes a within-interval arrival profile. The synthetic counter comparison uses uniform arrivals and constant per-molecule loss.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalWindow.at_start](../CellsProofs/Chemistry/ArrivalWindow.lean#L16)
- [CellsProofs.Chemistry.ArrivalWindow.at_end](../CellsProofs/Chemistry/ArrivalWindow.lean#L17)
- [CellsProofs.Chemistry.ArrivalWindow.adjacent](../CellsProofs/Chemistry/ArrivalWindow.lean#L20)
- [CellsProofs.Chemistry.ArrivalWindow.add_histories](../CellsProofs/Chemistry/ArrivalWindow.lean#L32)
- [CellsProofs.Chemistry.ArrivalWindow.reuse](../CellsProofs/Chemistry/ArrivalWindow.lean#L39)
- [CellsProofs.Chemistry.ArrivalWindow.chase_only](../CellsProofs/Chemistry/ArrivalWindow.lean#L44)
- [CellsProofs.Chemistry.ArrivalWindow.chase_fraction](../CellsProofs/Chemistry/ArrivalWindow.lean#L54)
- [CellsProofs.Chemistry.ArrivalWindow.empty_fraction](../CellsProofs/Chemistry/ArrivalWindow.lean#L59)
- [CellsProofs.Chemistry.ArrivalWindow.release_example](../CellsProofs/Chemistry/ArrivalWindow.lean#L63)

Proof sources [Mathlib product over the successor range, imported for survival across a chase](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L503) · [FR-42 boundary and reuse requirements](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [FR-38 clarification of release, survivors and the chase denominator](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/FEATURE_REQUESTS.md#fr-38--rna-release-from-its-template-into-two-pools-with-different-lifetimes)

Uses [Neutral arrival-time cohorts share one physical loss rate](fr42-cohort-shares.md)

## Numerical comparison

**Open.** For 10 releases, 8 remain at close and 6 later, giving 6/8. The reused label ends with 3 old plus 1 new. The compiled FR-38 development fixture routed all five steps to the expected classes in both fates with zero new chain completions. Its host reconstruction added both surviving histories within 2 × 10⁻¹⁴ relative tolerance. The FR-42 share-based engine and label-neutral energy comparison remain open.

**Reference calculation**

[Half-open windows and within-run label reuse](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [FR-38 release-marking and chase denominator](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/docs/FEATURE_REQUESTS.md#fr-38--rna-release-from-its-template-into-two-pools-with-different-lifetimes) · [Point-arrival recurrence and survival of the original cohort](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Host calculation for uniformly spread arrivals](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/validation/gene_regulation/cohort.py#L123-L180) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/arrival_windows.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr42-release-windows)

[Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[One-way release from the template hold into the scheduled class and fate](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/operators/templated_polymerisation.py#L1201-L1224) · [Template hold and release classes in the R1 world](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/worlds.py#L519-L558) · [Schedule controls on the engine grid](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/definitions/pump_composite_spec.py#L258) · [Public windowed engine execution](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/execution/windows.py) · [Compiled collection and class-specific release counters](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/engine_run.py#L393-L411) · [Observation horizon and grid of the starting fixture](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/kernel.py#L28-L36) · [Fate export and release-counter selection](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/cohort.py#L240-L310) · [Exact release-window and chase identities](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/arrival_windows.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr42-release-windows)

[Tested engine 57cf9a4ed0b6](https://github.com/Eidosoma/Cells/commit/57cf9a4ed0b68454232a3c531c14e1b725853955) · [Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

## Biological evidence

**Open.** Cohort membership requires the time of release from the template and survival of the same molecules to a later sample.

Bellecourt et al. measured detachment separately from synthesis. Their released-RNA fraction has a different denominator from survival of a release-marked cohort.

**Unit** Fraction (0–1)

### bellecourt-2019-hisl-release

In vitro bacterial transcription. The assay distinguished released terminator-length RNA and template-associated terminator-length RNA. The chase followed labelling of nascent RNA. Figure 5A and accompanying Results, with the time course in Figure S5 [Bellecourt et al. (2019), Journal of Molecular Biology 431, 696–713](https://doi.org/10.1016/j.jmb.2019.01.003)

- **Evidence role** descriptive
- **Observed** 0.94 Fraction (0–1)

The study reports ±0.02 for the wild-type release fraction under reducing conditions. Figure 5A pools the 120, 240 and 480 s samples.

This measures population detachment. Individual completion-to-release delays and later survival of the same released cohort remain unmeasured. [Dataset manifest](../checks/data/bellecourt2019_rna_release.json) · [Comparison verdict](../PROGRESS.md#fr42-release-windows)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
