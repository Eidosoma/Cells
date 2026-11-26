<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Daughter rupture at birth can be reconstructed from the shear records

Each retained daughter that ruptures returns its contents once. A single-lineage shear records the pool before the followed daughter releases. A population shear records the pool after all releases at that stop. Subtracting the finite receipts and adding back the signed reservoir debits recovers the starting balances.

## Assumptions

- Each daughter and each of its source places appears once with a nonnegative count. Its key identifies it across the stop, including when siblings from different parents occupy the same slot in succession. The recorded rupture and continuation flags determine which daughters release.
- Every source place has one pool destination for its species. Its finite or held status stays fixed. Division itself leaves the pool unchanged, and the earlier and later records bound the same shear event.
- Only retained daughters that rupture credit the modeled pool. An unfollowed daughter leaves the single-lineage system through its sink.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleRelease.birth_receipts](../CellsProofs/Chemistry/VesicleBirth.lean#L17)
- [CellsProofs.Chemistry.VesicleRelease.birth_pool_reconstruction](../CellsProofs/Chemistry/VesicleBirth.lean#L32)

Direct proof subject `cells.operator.shear_fission@1`, `cells.free_energy.osmotic_lumen@1`, `cells.population.shared_pool@1`

Proof sources [The Cells R9 release theorem supplies the accounting at a single destination](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/CellsProofs/Chemistry/VesicleRelease.lean#L29) · [Mathlib List.sum_append adds the receipts of consecutive daughters](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/List/Basic.lean#L43) · [Lean List.map_append preserves the source order within each daughter](https://github.com/leanprover/lean4/blob/v4.19.0/src/Init/Data/List/Lemmas.lean#L1805)

Uses [Terminal rupture accounts once for every molecule returned to its destination](vesicle-lysis-returns.md) · [Shear fission partitions the parent among all daughters and books discarded siblings](vesicle-shear-fission.md)

## Numerical comparison

**Checked.** Six compiled runs checked finite and held returns, an unfollowed rupture, consecutive daughters in a reused slot and two releases from one three-way split. An archived OL5 population shear independently supplied seven release rows. The finite lipid pool rose from 270 to 2,359, the solute pool from 0 to 55,631, and signed held lipid supply fell by 356.

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.ideal_mixing@1`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

**Operators** `cells.shear_fission@1`

[Daughter partition, identity and rupture flags](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/division.py#L410) · [Population split and daughter releases](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/population.py#L625) · [Shear events and daughter keys in the population record](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/diagnostic.py#L296) · [Run bundle writer and public row fields](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/records.py) · [Single-lineage split and continuation](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/runner.py#L290) · [Single-lineage shear diagnostic](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/src/cells/models/assembly_lineages_v2/diagnostic.py#L166) · [R10 interpretation of both modes](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/validation/assembly_lineages_v2/FORMAT_OL2.md#L570) · [Osmotic world fixture](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/tests/unit/test_assembly_lineages_v2_lumen.py) · [Compiled run definition](https://github.com/Eidosoma/Cells/blob/b99d63150e440e37fc3070d76053053c59b21973/tests/assembly_lineage_v2_fixtures.py) · [R9 molecule return proof](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/CellsProofs/Chemistry/VesicleRelease.lean) · [R10 reconstruction proof](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/CellsProofs/Chemistry/VesicleBirth.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/checks/vesicle_birth.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/PROGRESS.md#vesicle-birth-returns)

[Tested engine b99d63150e44](https://github.com/Eidosoma/Cells/commit/b99d63150e440e37fc3070d76053053c59b21973) · [Evidence checkpoint 1c0a315390b8](https://github.com/Eidosoma/Cells/commit/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0)

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.ideal_mixing@1`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

**Operators** `cells.shear_fission@1`

[Daughter partition, identity and rupture flags](https://github.com/Eidosoma/Cells/blob/e6571f88ead17ef235bd4fb2c1f26f387f7c1967/src/cells/models/assembly_lineages_v2/division.py#L410) · [Population split and daughter releases](https://github.com/Eidosoma/Cells/blob/e6571f88ead17ef235bd4fb2c1f26f387f7c1967/src/cells/models/assembly_lineages_v2/population.py#L625) · [Shear events and daughter keys in the population record](https://github.com/Eidosoma/Cells/blob/e6571f88ead17ef235bd4fb2c1f26f387f7c1967/src/cells/models/assembly_lineages_v2/diagnostic.py#L296) · [Run bundle writer and public row fields](https://github.com/Eidosoma/Cells/blob/e6571f88ead17ef235bd4fb2c1f26f387f7c1967/src/cells/models/assembly_lineages_v2/records.py) · [Registered population probe writer](https://github.com/Eidosoma/Cells/blob/e6571f88ead17ef235bd4fb2c1f26f387f7c1967/validation/assembly_lineages_v2/probes2.py#L314) · [R9 molecule return proof](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/CellsProofs/Chemistry/VesicleRelease.lean) · [R10 reconstruction proof](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/CellsProofs/Chemistry/VesicleBirth.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/checks/vesicle_birth.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0/lean/PROGRESS.md#vesicle-birth-returns)

[Tested engine e6571f88ead1](https://github.com/Eidosoma/Cells/commit/e6571f88ead17ef235bd4fb2c1f26f387f7c1967) · [Evidence checkpoint 1c0a315390b8](https://github.com/Eidosoma/Cells/commit/1c0a315390b83b69f0c244c98a27eba0d8c7f9a0)

## Biological evidence

**Open.** Tracer in the parent, each daughter and the surrounding liquid at an identified division with one ruptured daughter.

Deshpande et al. observed one daughter surviving as its sibling ruptured at a microfluidic Y-junction. The paper also reports paired sibling signals in successful divisions and external dye spreading averaged across events. The amount released to the bath by the identified daughter remains unmeasured in this comparison. [Sibling fates, Fig. 1d](https://ceesdekkerlab.nl/wp-content/uploads/2019/08/Mechanical-division-of-cell-sized-liposomes.pdf#page=2) · [Sibling signals, Fig. 3b](https://ceesdekkerlab.nl/wp-content/uploads/2019/08/Mechanical-division-of-cell-sized-liposomes.pdf#page=5) · [External dye, Fig. 4](https://ceesdekkerlab.nl/wp-content/uploads/2019/08/Mechanical-division-of-cell-sized-liposomes.pdf#page=6)

**Unit** tracer amount per compartment

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
