<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Size-triggered fission conserves each species under fixed-quota and independent partitions

Single-molecule growth and conservative division at the threshold cannot overshoot it. Ranking all occupied places selects exactly the declared quota. For a tracer species, fixed-quota sampling and independent per-molecule assignment give different probabilities of a tracer-free daughter, even when their mean allocations agree.

## Assumptions

- Each molecule occupies one place and belongs to one species. The second daughter receives the complement. A split acts at the threshold before further growth.
- The rank proof applies to any realized stable ordering and integer quota. The equal-subset probability assumes equiprobable rankings. The engine floors the float64 product of the fraction and the parent size.
- For the binomial probabilities each molecule independently enters the named daughter with the same probability p. Comparing a center branch to two pooled side branches also assumes p is represented by the center volume fraction.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.LineageFission.mem_rankedFirst](../CellsProofs/Chemistry/LineageFission.lean#L14)
- [CellsProofs.Chemistry.LineageFission.ranked_sizes](../CellsProofs/Chemistry/LineageFission.lean#L23)
- [CellsProofs.Chemistry.LineageFission.threshold_history](../CellsProofs/Chemistry/LineageFission.lean#L35)
- [CellsProofs.Chemistry.LineageFission.binary_inventory](../CellsProofs/Chemistry/LineageFission.lean#L42)
- [CellsProofs.Chemistry.LineageFission.fixed_quota_no_marker](../CellsProofs/Chemistry/LineageFission.lean#L65)
- [CellsProofs.Chemistry.LineageFission.fair_split_no_marker](../CellsProofs/Chemistry/LineageFission.lean#L79)
- [CellsProofs.Chemistry.LineageFission.independent_no_marker](../CellsProofs/Chemistry/LineageFission.lean#L93)
- [CellsProofs.Chemistry.LineageFission.binomial_moments](../CellsProofs/Chemistry/LineageFission.lean#L127)

Direct proof subject `cells.operator.size_threshold_fission@1`

Uses [Shear fission partitions the parent among all daughters and books discarded siblings](vesicle-shear-fission.md)

## Numerical comparison

**Checked.** For a parent with two marked and two unmarked molecules, the named daughter had zero markers in 4 of 24 fixed-half rankings and 4 of 16 independent fair assignments. Padded places, ties and adjacent float64 quotas matched the specification. Exact weighted enumeration at parent counts 7, 9 and 12 matched the binomial variances at p = 1/3.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`

**Operators** `cells.size_threshold_fission@1`

[Single-molecule threshold trigger](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/kernel.py#L299) · [Ranked and binomial partitions](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/fission.py#L120) · [Sibling counts from the actual partition](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/kernel.py#L365) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4231c96210f7d0f63206ca08b88affab48ac1717/lean/checks/lineage_fission.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4231c96210f7d0f63206ca08b88affab48ac1717/lean/PROGRESS.md#size-threshold-fission)

[Tested engine ea073ff872ec](https://github.com/Eidosoma/Cells/commit/ea073ff872ec64b34346fb01fdc40bb38c8f2861) · [Evidence checkpoint 4231c96210f7](https://github.com/Eidosoma/Cells/commit/4231c96210f7d0f63206ca08b88affab48ac1717)

## Biological evidence

**Open.** Variance of the center daughter's marked-particle count across divisions with a fixed reconstructed total.

**Unit** beads²

### fornell2017_passive_bead_partition@1

Water droplets containing polystyrene beads split into three daughters of approximately equal volume. All 180 plotted control splits contribute to the empty-center comparison. The sample variances use reconstructed totals of 7, 9 and 12 beads. Figure 2c on printed page 031101-3. The pale-blue series gives the ultrasound-off control. Both side outlets are pooled. [Fornell et al. (2017), Fig. 2c](https://doi.org/10.1063/1.4984131)

- **Evidence role** descriptive
- **Observed** 2.1818 beads²
- **Predicted** 2 beads²

At nine beads there are twelve plotted splits. The seven- and twelve-bead groups each contain seven splits. Counts were read from vector markers, including overlapping markers. Per-split volume fractions and raw paired counts are unavailable in the cited figure.

At nine beads the measured sample variance was 2.18, compared with 2.00 under independent assignment. At seven and twelve beads the measured values were 0.95 and 4.48, compared with 1.56 and 2.67. The 180 splits had zero empty centers. The nominal volume model gives a 26% probability of that outcome if splits are independent. The data leave independence and the engine’s size trigger unresolved. [Dataset manifest](../checks/data/fornell2017_partition.json) · [Comparison verdict](../PROGRESS.md#size-threshold-fission)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
