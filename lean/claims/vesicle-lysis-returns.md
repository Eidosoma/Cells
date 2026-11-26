<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Terminal rupture accounts once for every molecule returned to its destination

Starting at the triggering step’s own pool, each finite pool gains the molecules returned to it. Each held pool keeps its count and its signed reservoir supply decreases by the receipt. Summing the receipts over destinations accounts for the entire contents of the ruptured vesicle.

## Assumptions

- The source list is the membrane and lumen places of the ruptured vesicle. Each appears once with its nonnegative count after the triggering step. Each has exactly one destination pool for its species.
- The pool state used as the starting point already includes the triggering step. A destination has a fixed finite or held status during release. Counts lie in the engine’s admitted integer domain.
- The four comparisons use step-triggered lysis. A population lysis row belongs to the affected slot at that event. The held tracer in these fixtures has no other route for exchange.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleRelease.release_ledger](../CellsProofs/Chemistry/VesicleRelease.lean#L29)
- [CellsProofs.Chemistry.VesicleRelease.total_returned](../CellsProofs/Chemistry/VesicleRelease.lean#L45)

Direct proof subject `cells.free_energy.osmotic_lumen@1`, `cells.population.shared_pool@1`

Proof sources [Mathlib Finset.sum_ite_eq sums a receipt at its unique destination](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Piecewise.lean#L142) · [Mathlib Finset.sum_add_distrib separates a source contribution from the remaining receipts](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L268)

Uses [Changing molecular area units preserves the exact vesicle rupture decision](vesicle-lysis-threshold.md) · [Vesicles withdrawing from a finite shared bath conserve each species across the population](shared-pool-inventory.md)

## Numerical comparison

**Checked.** Four saved CPU runs reconciled by destination in single-lineage and population modes. Four membrane lipids and two lumen lipids returned to a pool holding one lipid, giving seven. Two impermeant tracers returned to a finite pool or reduced held supply by two with 9.210340371976182 kT of return work.

**Engine** `cells.assembly_lineages@2`, `cells.osmotic_lumen@1`, `cells.shared_pool@1`, `cells.phase_exchange@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Single-lineage material return](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/runner.py#L492) · [Population material return](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/population.py#L700) · [Diagnostic event counts](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/diagnostic.py) · [Published place table and bundle writer](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/records.py) · [Tension at the triggering step](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/lumen.py) · [R9 record definition](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/validation/assembly_lineages_v2/FORMAT_OL2.md#L545) · [Osmotic world fixture](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/tests/unit/test_assembly_lineages_v2_lumen.py) · [World and execution definition](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/tests/assembly_lineage_v2_fixtures.py) · [Release ledger proof](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/CellsProofs/Chemistry/VesicleRelease.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/checks/vesicle_release.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/PROGRESS.md#vesicle-lysis-returns)

[Tested engine 87e81f56366b](https://github.com/Eidosoma/Cells/commit/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25) · [Evidence checkpoint 7e126375842e](https://github.com/Eidosoma/Cells/commit/7e126375842ef23f0eb29734847cfe1dffd5ac4c)

## Biological evidence

**Open.** Paired counts in a vesicle and each recipient immediately across complete rupture, including the material recovered outside.

**Unit** molecules per destination

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
