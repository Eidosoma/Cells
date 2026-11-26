<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Serial transfer accounts for the spent bath and the vesicles removed

For each species, the new world plus the spent bath and removed vesicles contains the old world plus the fresh bath. Across consecutive washes, each slot retains its original cargo exactly when it is kept both times. The change in world free energy equals fresh-bath work minus the free energy exported.

## Assumptions

- A transfer is instantaneous. It replaces the finite bath with declared counts and keeps each sampled vesicle intact. The proof conditions on the selected slots.
- World free energy is the signed sum of the bath and individual live-vesicle free energies. Consecutive-wash composition assumes no intervening reaction or transport event.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePopulation.partition_slots](../CellsProofs/Chemistry/VesiclePopulation.lean#L16)
- [CellsProofs.Chemistry.VesiclePopulation.transfer_inventory](../CellsProofs/Chemistry/VesiclePopulation.lean#L27)
- [CellsProofs.Chemistry.VesiclePopulation.successive_transfers](../CellsProofs/Chemistry/VesiclePopulation.lean#L36)
- [CellsProofs.Chemistry.VesiclePopulation.transfer_free_energy](../CellsProofs/Chemistry/VesiclePopulation.lean#L44)

Direct proof subject `cells.operator.serial_transfer@1`

Uses [Vesicles withdrawing from a finite shared bath conserve each species across the population](shared-pool-inventory.md)

## Numerical comparison

**Checked.** Three compiled washes kept three of three, one of three, and one of one vesicles. All three species balanced exactly, including across two same-time schedules. The largest difference from independently calculated work, sink or world-energy change was 1.42 × 10⁻¹⁴ k_BT.

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

**Operators** `cells.serial_transfer@1`

[Rank the living slots by their draws](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/transfer.py#L81) · [Apply the sample, replace the bath and book work and sink](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/population.py#L588) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3/lean/checks/vesicle_population.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3/lean/PROGRESS.md#vesicle-serial-transfer)

[Tested engine 5011ed3d6bb6](https://github.com/Eidosoma/Cells/commit/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce) · [Evidence checkpoint 8b72a3ed05b9](https://github.com/Eidosoma/Cells/commit/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3)

## Biological evidence

**Open.** Tracer recovered in retained vesicles, the spent bath and removed vesicles across a wash, relative to the initial tracer and any fresh input.

**Unit** fraction of tracer input

### fayolle2018_serial_wash@1

Calcein-loaded DOPC/DOPA giant vesicles underwent successive dilution and microfiltration. The authors measured lipid in each retained fraction independently. Table 1 reports three successive retentates. Figure 3A–E shows calcein fluorescence inside and outside vesicles. [Fayolle et al. (2018), Table 1 and Fig. 3](https://doi.org/10.1371/journal.pone.0192975)

- **Evidence role** descriptive

The signal ratios have a reported ±20% uncertainty. Later exterior signals reached the detector floor. The table gives no lipid error bars.

Exterior clearance raised the lumen-to-exterior signal ratio to 39, 89 and 137. Cumulative lipid recoveries were 40%, 26% and 16%. The individual tracer amounts in the retained and discarded fractions remain unresolved. [Dataset manifest](../checks/data/vesicle_population_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-serial-transfer)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
