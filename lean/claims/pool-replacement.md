<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A finite-pool wash preserves assembly cargo and books the two bath energies

A replacement swaps the finite bath at one isolated stop. For each finite species, the inventory after the stop plus the removed bath equals the inventory before plus the supplied bath. A tracer-free wash leaves exactly the tracer retained by the slots available for later exchange. When bath and slot energies are additive, the change in total free energy equals fresh-bath work minus the spent-bath sink.

## Assumptions

- Each slot survives the stop. The pool volume is fixed and fresh finite counts fit the execution capacity. The signed energy calculation uses the same units and standard potentials on both sides.
- Between the wash and later observations, the tracer can move between bath and slots. Binding inside a slot preserves its tracer moiety. The history assumes no tracer source, sink, lysis or further wash.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePopulation.replacement_state](../CellsProofs/Chemistry/VesiclePopulation.lean#L131)
- [CellsProofs.Chemistry.VesiclePopulation.replacement_inventory](../CellsProofs/Chemistry/VesiclePopulation.lean#L134)
- [CellsProofs.Chemistry.VesiclePopulation.wash_history_inventory](../CellsProofs/Chemistry/VesiclePopulation.lean#L140)
- [CellsProofs.Chemistry.VesiclePopulation.replacement_energy](../CellsProofs/Chemistry/VesiclePopulation.lean#L147)

Direct proof subject `cells.operator.pool_replacement@1`

Uses [Vesicles withdrawing from a finite shared bath conserve each species across the population](shared-pool-inventory.md) · [Serial transfer accounts for the spent bath and the vesicles removed](vesicle-serial-transfer.md)

## Numerical comparison

**Checked.** In the two-vesicle CPU world a pulse supplied 12 tracer molecules. The wash removed six and retained six, including three bound to membrane sites. Tracer inventory closed exactly at all 856 saved rows. All six nonzero material edges matched the independently reconstructed receipts, and the maximum bath or world energy discrepancy was below 2.85 × 10⁻¹⁴ kBT. After washing at 2 s, release preceded uptake at 2.000848 s and 2.001470 s. The 21 November pulse-and-wash replay preserved the tracer ledger on all 856 rows with a maximum energy discrepancy of 2.85 × 10⁻¹⁴ kBT.

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.ideal_mixing@1`

**Operators** `cells.pool_replacement@1`, `cells.serial_transfer@1`

[Checks on every fresh count and founder](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/models/assembly_lineages_v2/spec.py#L692) · [Discrete ideal-bath energy](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/models/assembly_lineages_v2/ideal_mixing.py) · [Replacement and transfer schedule definitions](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/tests/unit/test_assembly_lineages_v2_replacement.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/pool_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-engine-review)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.transition_state_factor@1`

**Operators** `cells.pool_replacement@1`

[Fresh finite counts and per-species receipts](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/replacement.py#L81) · [Shared operation on finite pool places](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/transfer.py#L81) · [Two signed bath energy entries at the stop](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/population.py#L753) · [Saved per-species material edges](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/records.py#L511) · [Pulse and wash fixture](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/tests/unit/test_assembly_lineages_v2_replacement.py#L106) · [Independent dilute-bath free energy](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/checks/vesicle_population.py#L37) · [Vesicle wash and redistribution measurements](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/checks/data/pool_replacement_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/checks/pool_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/PROGRESS.md#pool-replacement)

[Tested engine 529070a8c844](https://github.com/Eidosoma/Cells/commit/529070a8c844ae8d58da615494df31f21ce49774) · [Evidence checkpoint 529070a8c844](https://github.com/Eidosoma/Cells/commit/529070a8c844ae8d58da615494df31f21ce49774)

## Biological evidence

**Open.** External tracer depletion, cargo retained by surviving vesicles, and redistribution to finite recipient membranes.

Giant vesicles retained fluorescent cargo after external label fell to near background. A separate liposome experiment measured transfer between finite donor and recipient membranes. The synthetic fixture’s return time and absolute retention remain uncalibrated.

**Unit** fluorescence units, fraction of total fluorescence, and elapsed time

### zhao_dextran_exchange@1

Trapped giant unilamellar vesicles containing fluorescent dextran. The replacement liquid contained the unlabelled polymers. Supporting Figure S3a–c and solution-exchange methods. [Zhao et al., supporting Figure S3a–c](https://doi.org/10.1002/adma.202106633)

- **Evidence role** descriptive

Three preparations, 3–4 measurements per position, error bars SD. Some vesicles were lost and no per-vesicle retained fraction was reported.

After 40 min of flow at 1 µL/min the exterior signal was approximately 0.1 fluorescence units while surviving vesicles retained fluorescent contents. [Dataset manifest](../checks/data/pool_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#pool-replacement)

### sumi_intervesicle_transfer@1

DOPC-based donor and acceptor liposomes. Acceptor material was twice the donor amount. Figure 7A and adjacent text on C6-NBD-PC exchange. [Sumi et al. (2017)](https://doi.org/10.1038/s41598-017-02980-x)

- **Evidence role** descriptive

The figure shows a representative trace from three experiments. The crossover has no reported uncertainty interval.

The signal reached about 48% of total fluorescence at 3.8 min. The assay resolves redistribution between populations. It does not identify a molecule returning to its original vesicle. [Dataset manifest](../checks/data/pool_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#pool-replacement)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
