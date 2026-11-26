<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Vesicles withdrawing from a finite shared bath conserve each species across the population

Each passive transfer changes one vesicle and the single bath by opposite integer counts. The inventory is conserved over every finite history of such transfers. Each live vesicle sees the same remaining bath density, and a permutation of the slots preserves the exact total rate.

## Assumptions

- Follow one conserved species at a time with a finite common bath. The count proof covers passive uptake and release. Chemical conversion, fission, lysis, bath replacement and external supply need their own accounting.
- A slot's uptake coefficient includes its own membrane geometry. The uptake-rate decrement in another slot assumes that slot's coefficient and the bath volume stay fixed. A relabelling carries occupancy and the full vesicle state together.
- For the experimental area comparison, both populations start with equal lipid amounts and share an area per molecule. A 25% donor loss predicts a 25% recipient gain conditional on zero net change of free lipid in the bath.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.SharedPool.event_inventory](../CellsProofs/Chemistry/SharedPool.lean#L24)
- [CellsProofs.Chemistry.SharedPool.history_inventory](../CellsProofs/Chemistry/SharedPool.lean#L29)
- [CellsProofs.Chemistry.SharedPool.population_uptake](../CellsProofs/Chemistry/SharedPool.lean#L40)
- [CellsProofs.Chemistry.SharedPool.depletion](../CellsProofs/Chemistry/SharedPool.lean#L46)
- [CellsProofs.Chemistry.SharedPool.relabel_rate](../CellsProofs/Chemistry/SharedPool.lean#L53)
- [CellsProofs.Chemistry.SharedPool.fractional_gain](../CellsProofs/Chemistry/SharedPool.lean#L58)

Direct proof subject `cells.population.shared_pool@1`

Uses [Lipid insertion scales with membrane area and diffusion-limited capture scales with radius](vesicle-phase-exchange.md) · [Neutral solute entry scales with area and spherical washout with inverse radius](vesicle-permeation.md)

## Numerical comparison

**Checked.** Two 96-event osmotic populations conserved one lipid and one solute across every recorded row. All six slot permutations preserved the corresponding rates. The repaired reporter also returned the one-event population with its declared 10⁻²² L lumen. The earlier records retain the reporting failure.

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Shared-pool output assembly](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/population.py) · [Osmotic volume parameters](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py) · [Dispatch by execution mode](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [test assembly lineages v2 geometry](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_geometry.py) · [vesicle exchange measurements](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/vesicle_exchange_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/shared_pool.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.stochastic_mass_action@1`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Population records for osmotic and declared lumens](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/models/assembly_lineages_v2/population.py#L824) · [Volume and tension columns](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/models/assembly_lineages_v2/population.py#L846) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/checks/shared_pool.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/PROGRESS.md#claim-source-review)

[Tested engine dd085e36e9ce](https://github.com/Eidosoma/Cells/commit/dd085e36e9ced2edfed88c7194e970bd335f3ad0) · [Evidence checkpoint 8f269af4c8b7](https://github.com/Eidosoma/Cells/commit/8f269af4c8b79150020b47a86dd71da848d91714)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Shared-pool output assembly](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/models/assembly_lineages_v2/population.py#L735) · [Osmotic volume parameters](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/shared_pool.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#vesicle-threshold-hold)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.stochastic_mass_action@1`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Pool and live-slot rates](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/population.py#L187) · [One pool and one slot updated per event](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/population.py#L220) · [Counts saved and checked against the device endpoint](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/population.py#L669) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/checks/shared_pool.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/PROGRESS.md#shared-pool-inventory)

[Tested engine 3d3d9641932a](https://github.com/Eidosoma/Cells/commit/3d3d9641932a52852727df7e4722e15ded245766) · [Evidence checkpoint 19de00d9a76a](https://github.com/Eidosoma/Cells/commit/19de00d9a76a27fd064f1e643be28db630d48423)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Accepted population inputs](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/population.py#L54) · [Dispatch by execution mode](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/runner.py#L343) · [Volume reported for every live slot](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/population.py#L717) · [Outside osmolarity used by the volume calculation](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/checks/shared_pool.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/PROGRESS.md#shared-pool-declared-volume)

[Tested engine 3d3d9641932a](https://github.com/Eidosoma/Cells/commit/3d3d9641932a52852727df7e4722e15ded245766) · [Evidence checkpoint 19de00d9a76a](https://github.com/Eidosoma/Cells/commit/19de00d9a76a27fd064f1e643be28db630d48423)

## Biological evidence

**Open.** Paired changes in donor and recipient membrane area during passive competition, with independent measurement of material left in the common bath.

**Unit** % recipient area change

### chen2004_oleate_competition@1

Matched experiments label either the isotonic donor or the osmotically swollen recipient population of oleate vesicles. Figures 1B and 1D and the accompanying 1:1 mixing result on page 1475. [Chen, Roberts and Szostak (2004), Figs. 1B and 1D](https://doi.org/10.1126/science.1100757)

- **Evidence role** descriptive
- **Observed** 25 % recipient area change
- **Predicted** 25 % recipient area change

Both area changes are approximate. Figure 1 gives no endpoint uncertainty. Fluorescence reports area and the free lipid pool was unmeasured.

The measured donor loss gives the conditional recipient gain shown. The experiment supports redistribution between populations. An empirical test of molecule closure still needs independent counts for donor, recipient and bath. [Dataset manifest](../checks/data/vesicle_exchange_measurements.json) · [Comparison verdict](../PROGRESS.md#shared-pool-inventory)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
