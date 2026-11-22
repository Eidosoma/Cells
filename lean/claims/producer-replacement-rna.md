<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# RNA removed at replacement is accounted for under its departing producer

For one cell, generation and chain, the initial hold and fate stocks plus completions equal the final hold and fate stocks plus degradation. At replacement each departing stock keeps its pre-event label, including any material supplied with the base label. The newcomer’s production counters measure increments since its own birth.

## Assumptions

- One producer supplies the two fate rows during its lifetime. Every detachment and degradation is included. The intracellular balance assumes no external mover.
- Replacement removes the whole hold and the two fate rows. The holds and rows have disjoint owners. Each occupied pool’s label shares sum to one, and a newcomer has no share of previously labelled material.
- A generation’s counter is the difference of the cumulative values at observation and birth. The live state holds the latest departed total. Reading each departure directly requires a saved observation before that record is overwritten.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ProducerReplacement.at_birth](../CellsProofs/Chemistry/ProducerReplacement.lean#L20)
- [CellsProofs.Chemistry.ProducerReplacement.generation_totals](../CellsProofs/Chemistry/ProducerReplacement.lean#L23)
- [CellsProofs.Chemistry.ProducerReplacement.generation_balance](../CellsProofs/Chemistry/ProducerReplacement.lean#L32)
- [CellsProofs.Chemistry.ProducerReplacement.disjoint_removals](../CellsProofs/Chemistry/ProducerReplacement.lean#L48)
- [CellsProofs.Chemistry.ProducerReplacement.removal_total](../CellsProofs/Chemistry/ProducerReplacement.lean#L55)
- [CellsProofs.Chemistry.ProducerReplacement.absent_at_removal](../CellsProofs/Chemistry/ProducerReplacement.lean#L65)

Direct proof subject `cells.templated_polymerisation@1`, `cells.scheduled_cell_replacement@1`, `cells.neutral_arrival_labels@1`

Proof sources [Mathlib finite telescoping sum, specialized to generation counter increments](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L859-L864) · [Mathlib sum over a disjoint union, specialized to each label’s removal](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L113-L116) · [Mathlib multiplication distributed over a finite sum](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Ring/Finset.lean#L48-L52) · [Cells replacement and birth-counter definitions](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1483-L1515) · [Mathlib interchange of finite sums for summing removals across labels](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Sigma.lean#L116-L119)

Uses [Marked RNA is accounted for in both release fates, including after label reuse](release-window-survival.md) · [Simultaneous replacement books the old and arriving species, charge and electrical work](scheduled-cell-replacement.md)

## Numerical comparison

**Open.** Public main at 0a1c1b0d correctly refused this composition. On development revision 4099775c, the native JSON recorded nine passing verdicts and the checkpoint restart reproduced the step histories bit for bit. The independent replay checked seven birth offsets and twelve departing amounts by label. The largest hold or fate balance residual was 1.02 × 10⁻²¹ fmol. Swapping the founder’s marked durable RNA into the newcomer’s label preserved total mass while misassigning 4.11 × 10⁻⁸ fmol. The repaired report writer preserved all 217 checkpoint arrays byte for byte relative to the first development replay. The positive comparison on public main and extracellular RNA retention remain open.

**Reference calculation**

[Per-producer counters and replacement balance](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1483-L1515) · [Division of the event reports between the two owners](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1773-L1787) · [Cells writes the numerical state and clock to its checkpoint](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/src/cells/records/io.py#L86) · [Reference copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/validation/gene_regulation/sheet_check.py#L96) · [Exact per-producer balance and label partition](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/PROGRESS.md#fr38-producer-replacement)

[Evidence checkpoint 36f778812782](https://github.com/Eidosoma/Cells/commit/36f778812782bc352a9fe3666c579b85bc87ca28)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

[Public guard on templated polymerisation with replacement](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/operators/templated_polymerisation.py#L969) · [Definition with a replacement and expected refusal](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/unit/test_templated_polymerisation.py#L181) · [RNA fixture](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/validation/gene_regulation/worlds.py#L543) · [Replacement template and event fixture](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/validation/tissue/secreted_species_fixtures.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/tests/unit/test_templated_polymerisation.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/PROGRESS.md#fr38-producer-replacement)

[Tested engine 0a1c1b0dc814](https://github.com/Eidosoma/Cells/commit/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe) · [Evidence checkpoint 36f778812782](https://github.com/Eidosoma/Cells/commit/36f778812782bc352a9fe3666c579b85bc87ca28)

## Biological evidence

**Open.** Source-specific RNA measured before and after a change of producer, distinguishing removal from degradation and any RNA remaining outside the cell.

Placental lactogen RNA remained detectable in some maternal plasma samples after delivery. The time and source tissue are identifiable. The age of each molecule, its cell of origin and the contributions of release near delivery remain unresolved.

**Unit** RNA in fmol by producer in Cells. The plasma study reports copies per mL and the number of women with detectable RNA.

### ng-2003-postpartum-hpl

Paired maternal plasma samples at term, one before delivery and one afterwards. The two-hour group had a median 24,499 hPL mRNA copies/mL before delivery. Figure 4C for two hours and Figure 4A for the separate 24-hour group, with the accompanying Results. [Ng et al. (2003), PNAS 100, 4748–4753](https://doi.org/10.1073/pnas.0637450100)

- **Evidence role** descriptive

The Wilson 95% interval for the two-hour detection fraction, calculated from the published counts, is 12.7–57.6%. In the four detectable pairs, concentrations declined by approximately 66–97% from their own baselines.

At two hours 4 of 13 women had detectable hPL RNA. A separate group had 0 of 8 detectable at 24 hours. These observations constrain how long a source-specific signal can remain detectable in plasma. Connecting them to the engine requires an extracellular compartment with measured transfer and clearance. [Dataset manifest](../checks/data/ng2003_postpartum_rna.json) · [Comparison verdict](../PROGRESS.md#fr38-producer-replacement)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
