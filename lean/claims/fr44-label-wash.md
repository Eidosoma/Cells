<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A compartment wash accounts for each tracer label in the sample and the well

A well-mixed withdrawal of amount $r$ from a pool of amount $n$ collects $rs$ of a label with initial share $s$. The well keeps $(n-r)s$ and credits all the incoming unlabelled material to the base. For each label, the amount after the wash plus the collected amount equals its starting amount plus its refill.

## Assumptions

- The finite set of declared labels includes the base. Starting shares are nonnegative and sum to one. The withdrawal is between zero and the starting amount, and the supply is nonnegative. Amounts use one common unit.
- The event samples a well-mixed pool, with no preferential loss by label. An empty post-wash pool may retain bookkeeping shares that represent zero material. A complete exchange with positive refill puts every unit in the base.
- For the dilution comparison the carrier concentration is the same before the wash and in its refill, which carries no tracer. Fixed volume makes the original-material concentration ratio equal to its fraction of the starting carrier. Reading fluorescence as this ratio also requires a linear optical response.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CompartmentWash.label_total](../CellsProofs/Tissue/CompartmentWash.lean#L81)
- [CellsProofs.Tissue.CompartmentWash.label_inventory](../CellsProofs/Tissue/CompartmentWash.lean#L88)
- [CellsProofs.Tissue.CompartmentWash.label_shares_sum](../CellsProofs/Tissue/CompartmentWash.lean#L102)
- [CellsProofs.Tissue.CompartmentWash.whole_label_share](../CellsProofs/Tissue/CompartmentWash.lean#L111)
- [CellsProofs.Tissue.CompartmentWash.unchanged_label_share](../CellsProofs/Tissue/CompartmentWash.lean#L116)
- [CellsProofs.Tissue.CompartmentWash.dilution_of_nonbase](../CellsProofs/Tissue/CompartmentWash.lean#L124)

Direct proof subject `cells.operator.scheduled_compartment_wash@1`, `cells.operator.neutral_arrival_labels@1`

Proof sources [Mathlib finite sum of scaled shares, imported and specialized](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Ring/Finset.lean#L51-L52) · [Mathlib single-index sum, imported to allocate the refill to the base](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Piecewise.lean#L150-L157) · [Mathlib sum of quotients, imported to normalize the shares](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Field.lean#L22-L24) · [Cells wash and label convention](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/docs/library/cells/operators/neutral_arrival_labels@1.md#L84-L100)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md) · [Neutral arrival-time cohorts share one physical loss rate](fr42-cohort-shares.md)

## Numerical comparison

**Checked.** One compiled CPU float64 run on 3552e6cd applied twelve exchanges across four isolated wells. Each started with 1 fmol of tagged carrier. The largest absolute per-label balance residual was 4.44 × 10⁻¹⁶ fmol. The nine exchange controls and the compiled labelled/unlabelled twin regression also passed, including exact clearance of every non-base share on a whole wash with positive supply.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.neutral_arrival_labels@1`

[Native liquid-exchange normalization](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/numerics/label_shares.py#L159-L182) · [Cumulative removal at the pre-wash label shares](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/operators/species_labels.py#L936-L951) · [Sample and supply from each scheduled event](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/operators/wash_schedule.py#L26-L33) · [Composite dispatch of a wash report to the label owner](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/models/pump_composite.py#L1677-L1687) · [Tissue model wrapped as a composition](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/definitions/pump_composite_spec.py#L276-L301) · [Compiled run entry point](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/src/cells/execution/runner.py#L393) · [Scheduled wash fixture](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/validation/tissue/wash_schedule_fixtures.py#L35-L45) · [Finite tissue nodes and carrier](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/validation/tissue/secreted_species_fixtures.py#L92-L115) · [Independent exchange controls](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/tests/unit/test_neutral_arrival_labels.py#L417-L459) · [Compiled labelled and unlabelled twins](https://github.com/Eidosoma/Cells/blob/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b/tests/unit/test_neutral_labels_events.py#L163-L225) · [Exact balance and dilution proofs](https://github.com/Eidosoma/Cells/blob/42120364522c140f99bc8d7701ad00d96386b3b2/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Vloemans single-step readings](https://github.com/Eidosoma/Cells/blob/42120364522c140f99bc8d7701ad00d96386b3b2/lean/checks/data/vloemans2024_dilution.json) · [Stubbington same-chamber readings](https://github.com/Eidosoma/Cells/blob/42120364522c140f99bc8d7701ad00d96386b3b2/lean/checks/data/stubbington2018_wash.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/42120364522c140f99bc8d7701ad00d96386b3b2/lean/checks/label_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/42120364522c140f99bc8d7701ad00d96386b3b2/lean/PROGRESS.md#fr44-label-wash)

[Tested engine 3552e6cd19dd](https://github.com/Eidosoma/Cells/commit/3552e6cd19ddd1b3c12f709dd48df24b7a9aba6b) · [Evidence checkpoint 42120364522c](https://github.com/Eidosoma/Cells/commit/42120364522c140f99bc8d7701ad00d96386b3b2)

## Biological evidence

**Open.** Normalized tracer signal in the retained liquid, paired with the amount of tracer in the withdrawal from the same exchange. The independent studies both measure dilution. A same-chamber assay of both inventories remains open.

- [Mixing retained fluorescein solution with tracer-free liquid lowers its normalized signal.](../WET_LAB_EVIDENCE.md#pair-blank-refill-tracer-dilution) · Supported by both studies
- [Tracer in the collected liquid and tracer left in the original chamber together account for the starting tracer after one well-mixed withdrawal and blank refill.](../WET_LAB_EVIDENCE.md#pair-same-wash-collected-and-retained-tracer) · Comparison unresolved

**Unit** fraction of starting tracer signal

### vloemans2024-dilution

Aliquots of diverted stock and the diluted metered plug were assayed on the same chip using calibrated fluorescein fluorescence. The 5, 2 or 1 µL metered volumes were mixed downstream with 5, 8 or 9 µL of PBS. Fig. 2A shows the split, Fig. 4A the single-step concentrations, and supplement §S2 the adsorption check. [Vloemans et al. (2024), Fig. 4A](https://doi.org/10.1039/D4LC00195H)

- **Evidence role** descriptive

Fig. 4A shows one SD with at least three replicates. The paper reports CV below 7%. Printed mean concentrations yield the ratios. The stored excess and downstream plug were sampled as aliquots, without total tracer recovery for the device.

The measured plug/stock ratios were 0.498, 0.193 and 0.093. The compiled equivalents were 0.500, 0.200 and 0.100. These are the same chip data already cited for the compartment-wash claim. Wall adsorption was measured. [Dataset manifest](../checks/data/vloemans2024_dilution.json) · [Comparison verdict](../PROGRESS.md#fr44-label-wash)

### stubbington2018-chamber-wash

A pipette replaced 20% of the solution in one PDMS chamber with pure water at each wash. Confocal imaging after equilibration measured fluorescein signal at one focal plane. Fig. 3.6, printed p. 36. Markers run from zero to nine exchanges. At ten washes the figure has only a reference line. [Stubbington (2018), §3.3.3, Fig. 3.6](https://etheses.durham.ac.uk/id/eprint/12771/1/ThesisLS_final.pdf#page=61)

- **Evidence role** descriptive

Graph readings are approximate to 0.01. Error bars denote SEM over three repeats, about 0.11 at wash one and 0.06 at wash five. The author discusses possible optical nonlinearity at late washes. No withdrawal assay was reported.

At washes one, five and nine the normalized signal was about 0.90, 0.21 and 0.05. Cells gave 0.800, 0.328 and 0.134. The late measured signal falls below the ideal concentration curve. The plotted reference matches 0.8ⁿ. Printed Eq. 3.7 would increase under the stated definition of the exchanged fraction. [Dataset manifest](../checks/data/stubbington2018_wash.json) · [Comparison verdict](../PROGRESS.md#fr44-label-wash)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
