<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Returning membrane area can leave some of its channels in the receiving pool

Retrieval carries away source-specific capacitance and leaves each population proportional to the remaining area fraction raised to its enrichment. Transfers conserve area, capacitance and each channel population. Returning the same area from a seeded, uniformly mixed pool leaves a positive share of the retrieved cohort inside.

## Assumptions

- A positive source area remains after each transfer. Enrichments are nonnegative, constant over the compared stages and refer to the population at its source patch.
- The round-trip formula uses uniform retrieval and recycling for the tracked cohort, a positive seed area, no initial internal cohort and no production or removal during the cycle.

## Lean proof

**Proved**

- [CellsProofs.Tissue.MembraneTrafficking.patch_balance](../CellsProofs/Tissue/MembraneTrafficking.lean#L40)
- [CellsProofs.Tissue.MembraneTrafficking.remaining_specific_capacitance](../CellsProofs/Tissue/MembraneTrafficking.lean#L43)
- [CellsProofs.Tissue.MembraneTrafficking.retained_bounds](../CellsProofs/Tissue/MembraneTrafficking.lean#L53)
- [CellsProofs.Tissue.MembraneTrafficking.same_direction_stages](../CellsProofs/Tissue/MembraneTrafficking.lean#L59)
- [CellsProofs.Tissue.MembraneTrafficking.surface_and_pool](../CellsProofs/Tissue/MembraneTrafficking.lean#L63)
- [CellsProofs.Tissue.MembraneTrafficking.round_trip_pool](../CellsProofs/Tissue/MembraneTrafficking.lean#L68)
- [CellsProofs.Tissue.MembraneTrafficking.round_trip_pool_pos](../CellsProofs/Tissue/MembraneTrafficking.lean#L77)

Direct proof subject `cells.operator.scheduled_membrane_trafficking@1`

Uses [Each compartment belongs to one cell and its charge sets its lumen voltage](owned-compartment-inventory.md) · [At fixed channel drive, whole-patch flow tracks the surface unit count](membrane-population-flow.md)

## Numerical comparison

**Checked.** A four-step cycle recovered all retrieved area. Of the initial 3,261.27 Kir units, 444.72 (13.64%) stayed in the pool. Two populations followed independent enrichment and recycling predictions within 3.42 × 10⁻¹³ units. The plasma gained 2.224 pF from mixing with a pool of higher specific capacitance. A separate extreme depletion comparison is recorded under empty-surface-flow.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kir2p1_mh2@1`, `cells.nav1p2_m3h_regularized@1`

**Operators** `cells.scheduled_membrane_trafficking@1`, `cells.cell_owned_compartments@1`, `cells.membrane_entity_state@1`

[Transferred area, capacitance and enriched cargo](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_trafficking.py#L627) · [Population and patch ledgers](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_trafficking.py#L804) · [Declared surface stock](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_state.py#L151) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/checks/compartment_trafficking.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/PROGRESS.md#membrane-retrieval-recycling)

[Tested engine b30e3298523e](https://github.com/Eidosoma/Cells/commit/b30e3298523e49bd6c33bba01aa11561f8fba449) · [Evidence checkpoint bad3c2a2f8b6](https://github.com/Eidosoma/Cells/commit/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5)

## Biological evidence

**Open.** Time-resolved membrane area or capacitance, internal cargo, and surface cargo of the same cohort during retrieval and recycling.

- [Some previously surface-exposed neurotransmitter receptors return to the membrane after internalization.](../WET_LAB_EVIDENCE.md#pair-receptor-return-to-surface) · Supported by both studies

Independent neuronal AMPA and muscle nicotinic receptor preparations both detected previously exposed receptors returning to the surface. Neither closes the full membrane-area and receptor-pool balance.

**Unit** pF and fraction of labelled cargo

### ojima2021_ampar_recycling@1

Endogenous AMPA receptors in basal primary hippocampal neuronal cultures. The snapshot uses whole-cell label. The chase uses a reference surface signal. Fig. 5c–d for the snapshot and Fig. 5e for recycling in a separate chase. [Ojima et al. (2021), Fig. 5c–e](https://doi.org/10.1038/s41467-021-21082-x)

- **Evidence role** descriptive

Mean ± SEM, three biological replicates for each measurement.

After 10 h of labelling, 90.4 ± 0.6% of the label was at the surface and 10.3 ± 1.7% was internal. In the 15 min chase, resurfaced label was 12.5 ± 2.8% of the reference surface signal. The missing terminal internal stock prevents a closed recycling balance. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#membrane-retrieval-recycling)

### okamoto2016_retrieved_membrane@1

Stimulated calyces of Held in brainstem slices at room temperature. Each readout is normalized to its own peak excess. Fig. 1C–E, peak capacitance and the fractions of capacitance and synaptotagmin-2 fluorescence remaining 60 s after stimulation. [Okamoto et al. (2016), Fig. 1C–E](https://doi.org/10.7554/eLife.14643)

- **Evidence role** descriptive

Mean ± SEM across seven capacitance and ten fluorescence recordings. Seven were simultaneous. Fluorescence depends on vesicle re-acidification.

After a 1.52 ± 0.21 pF capacitance rise, 0.33 ± 0.06 of peak excess capacitance and 0.47 ± 0.07 of peak fluorescence remained at 60 s. These measurements constrain net retrieval and cargo recovery separately. Absolute internal channel counts remain open. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#membrane-retrieval-recycling)

### bruneau2005_achr_recycling@1

Adult mouse sternomastoid endplates. Repeat surface labelling distinguishes previously exposed receptors that resurfaced from newly inserted receptors. Figure 7A–B and Results, days 1 and 4 after transient receptor block [Bruneau et al. (2005), Fig. 7A–B](https://doi.org/10.1523/JNEUROSCI.3169-05.2005)

- **Evidence role** descriptive

Four-day values and SDs from Results. The graph shows SEM. The denominator is the initial surface fluorescence. The study did not measure the final size of the internal receptor pool or the area of membrane returned.

At four days, resurfaced receptors contributed 26 ± 5% of the original surface fluorescence and newly inserted receptors 24 ± 5% (SD, 29 junctions). The original and recycled tags were distinguished experimentally. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
