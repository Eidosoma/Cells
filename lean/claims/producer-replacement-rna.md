<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# RNA keeps its producer label through export, cell replacement and return

For one producer label, combining the cell and outside-node balances cancels both directions of transport. Intracellular and extracellular degradation and the departure record each stay in the balance. The original producer’s stock in a new cell is at most cumulative gross return since replacement.

## Assumptions

- Each gross transfer carries the share of its source. A cell replacement books all departing intracellular stock and leaves the extracellular pool and its labels in place.
- The new cell starts with zero of the old producer label. Its only source of that label after replacement is reverse transport. Gross amount returned and all other outflows are nonnegative and the source share is at most one.
- The earlier no-export specialization assumes one producer per fate row over its lifetime. Generation counters use their birth offsets. Normalized shares split the departed material across labels.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ProducerReplacement.at_birth](../CellsProofs/Chemistry/ProducerReplacement.lean#L21)
- [CellsProofs.Chemistry.ProducerReplacement.generation_totals](../CellsProofs/Chemistry/ProducerReplacement.lean#L24)
- [CellsProofs.Chemistry.ProducerReplacement.generation_balance](../CellsProofs/Chemistry/ProducerReplacement.lean#L33)
- [CellsProofs.Chemistry.ProducerReplacement.disjoint_removals](../CellsProofs/Chemistry/ProducerReplacement.lean#L49)
- [CellsProofs.Chemistry.ProducerReplacement.removal_total](../CellsProofs/Chemistry/ProducerReplacement.lean#L56)
- [CellsProofs.Chemistry.ProducerReplacement.absent_at_removal](../CellsProofs/Chemistry/ProducerReplacement.lean#L66)
- [CellsProofs.Chemistry.ProducerReplacement.cell_node_balance](../CellsProofs/Chemistry/ProducerReplacement.lean#L76)
- [CellsProofs.Chemistry.ProducerReplacement.old_stock_le_returned](../CellsProofs/Chemistry/ProducerReplacement.lean#L86)

Direct proof subject `cells.operator.templated_polymerisation@1`, `cells.operator.scheduled_cell_replacement@1`, `cells.operator.neutral_arrival_labels@1`

Proof sources [Mathlib finite telescoping sum, specialized to generation counter increments](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L859-L864) · [Mathlib sum over a disjoint union, specialized to each label’s removal](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L113-L116) · [Mathlib multiplication distributed over a finite sum](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Ring/Finset.lean#L48-L52) · [Cells replacement and birth-counter definitions](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1483-L1515) · [Mathlib interchange of finite sums for summing removals across labels](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Sigma.lean#L116-L119) · [Mathlib finite-sum induction for the cumulative return bound](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L501-L505)

Uses [Marked RNA is accounted for in both release fates, including after label reuse](release-window-survival.md) · [Simultaneous replacement books the old and arriving species, charge and electrical work](scheduled-cell-replacement.md)

## Numerical comparison

**Checked.** All 14 development-fixture checks passed on public Cells at fd2bb88c. The separate registered FR-38 comparison failed R1 and found R2 inconclusive (D313). The non-blind follow-up traced route 1 to gross cohort loss in the engine and net loss in the reference (D316). At the checkpoint, 1.0534 × 10⁻²⁶ fmol of founder RNA was inside the new cell after 1.1173 × 10⁻²⁶ fmol had returned. The combined durable RNA inventory closed within 6.01 × 10⁻²³ fmol. Exchanging two outside labels kept total RNA identical and misplaced 8.114 × 10⁻⁹ fmol. The reader detected it. The three standard retention outputs had finite bounds. Sparse-grid behavior is recorded separately.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `templated_polymerisation@1`, `scheduled_cell_replacement@1`, `neutral_arrival_labels@1`

[Native replacement and restart fixture](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/validation/gene_regulation/replace_restart.py#L283) · [Known-rate reconstruction](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/validation/gene_regulation/cohort.py#L170) · [Gross export counters and loss at the outside node](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/operators/templated_polymerisation.py#L2470) · [Derived producer labels](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/operators/species_labels.py#L296) · [Two producers at one node](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/tests/unit/test_templated_polymerisation.py#L715) · [Per-label conservation and cumulative return bound](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/PROGRESS.md#fr38-extracellular-producer)

[Tested engine fd2bb88ce444](https://github.com/Eidosoma/Cells/commit/fd2bb88ce444b48344236024a2a18844f59041a4) · [Evidence checkpoint d2258d4f81a5](https://github.com/Eidosoma/Cells/commit/d2258d4f81a5a6e4a04277b51df0217e0b044289)

**Reference calculation**

[Per-producer counters and replacement balance](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1483-L1515) · [Division of the event reports between the two owners](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1773-L1787) · [Cells writes the numerical state and clock to its checkpoint](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/src/cells/records/io.py#L86) · [Reference copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/validation/gene_regulation/sheet_check.py#L96) · [Exact per-producer balance and label partition](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/PROGRESS.md#fr38-producer-replacement)

[Evidence checkpoint 36f778812782](https://github.com/Eidosoma/Cells/commit/36f778812782bc352a9fe3666c579b85bc87ca28)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

[Public guard on templated polymerisation with replacement](https://github.com/Eidosoma/Cells/blob/1e72a71b2d08408ce007276a187041a5e197cfad/src/cells/operators/templated_polymerisation.py#L969) · [Definition with a replacement and expected refusal](https://github.com/Eidosoma/Cells/blob/1e72a71b2d08408ce007276a187041a5e197cfad/tests/unit/test_templated_polymerisation.py#L181) · [RNA fixture](https://github.com/Eidosoma/Cells/blob/1e72a71b2d08408ce007276a187041a5e197cfad/validation/gene_regulation/worlds.py#L543) · [Replacement template and event fixture](https://github.com/Eidosoma/Cells/blob/1e72a71b2d08408ce007276a187041a5e197cfad/validation/tissue/secreted_species_fixtures.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/2f6f4808e861935a9933feb3027f66d008eda7e3/tests/unit/test_templated_polymerisation.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/2f6f4808e861935a9933feb3027f66d008eda7e3/lean/PROGRESS.md#fr38-producer-replacement)

[Tested engine 1e72a71b2d08](https://github.com/Eidosoma/Cells/commit/1e72a71b2d08408ce007276a187041a5e197cfad) · [Evidence checkpoint 2f6f4808e861](https://github.com/Eidosoma/Cells/commit/2f6f4808e861935a9933feb3027f66d008eda7e3)

## Biological evidence

**Open.** Source-specific RNA measured before and after a change of producer, distinguishing removal from degradation and any RNA remaining outside the cell.

Placental RNA can persist in plasma after delivery. In a separate cell preparation with donor cells absent, recipient cells genetically unable to produce the assayed RNA carried donor-derived molecules. The gross return rate across a cell replacement remains open.

**Unit** fmol or copy-equivalents by producer in Cells. Human plasma detection counts and donor miRNA copies per recipient cell in the studies.

### ng-2003-postpartum-hpl

Paired maternal plasma samples at term, one before delivery and one afterwards. The two-hour group had a median 24,499 hPL mRNA copies/mL before delivery. Figure 4C for two hours and Figure 4A for the separate 24-hour group, with the accompanying Results. [Ng et al. (2003), PNAS 100, 4748–4753](https://doi.org/10.1073/pnas.0637450100)

- **Evidence role** descriptive

The Wilson 95% interval for the two-hour detection fraction, calculated from the published counts, is 12.7–57.6%. In the four detectable pairs, concentrations declined by approximately 66–97% from their own baselines.

At two hours 4 of 13 women had detectable hPL RNA. A separate group had 0 of 8 detectable at 24 hours. The assay measures a source-specific population signal. A quantitative comparison needs matched transfer and clearance measurements. [Dataset manifest](../checks/data/ng2003_postpartum_rna.json) · [Comparison verdict](../PROGRESS.md#fr38-producer-replacement)

### alexander-2015-donor-mir146a

Native mouse miR-146a in recipient dendritic cell lysates 24 h after exposure to donor-derived extracellular vesicles. Donor cells were absent. Recipient cells lacked the assayed RNA gene. Vesicles from donor-null cells served as a control. Figures 3c–l and 4i. Figure 3l gives the copy count. [Alexander et al. (2015), Nature Communications 6, 7321](https://doi.org/10.1038/ncomms8321)

- **Evidence role** descriptive

Three replicates, with SD plotted. The numerical SD was not extracted. The copy count may include RNA bound to the cell surface.

Recipients averaged about 370 donor copies per cell. A reporter supported functional intracellular access. The endpoint supports donor attribution and leaves the uptake rate and post-wash persistence unresolved. [Dataset manifest](../checks/data/alexander2015_donor_rna.json) · [Comparison verdict](../PROGRESS.md#fr38-extracellular-producer)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
