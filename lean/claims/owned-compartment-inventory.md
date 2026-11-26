<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Each compartment belongs to one cell and its charge sets its lumen voltage

Summing each cell's cytosol with the compartments it owns counts every species amount once. A lumen with a single bounding capacitor sits above its owner's potential by its net free charge divided by that capacitance.

## Assumptions

- Each finite lumen has exactly one owner and positive bounding capacitance. The voltage formula assumes that its bounding membrane supplies its only capacitor plate.
- In the numerical comparison each cell and lumen exchange material externally only with their own held bath.

## Lean proof

**Proved**

- [CellsProofs.Tissue.MembraneTrafficking.sum_owners](../CellsProofs/Tissue/MembraneTrafficking.lean#L18)
- [CellsProofs.Tissue.MembraneTrafficking.lumen_potential](../CellsProofs/Tissue/MembraneTrafficking.lean#L27)
- [CellsProofs.Tissue.MembraneTrafficking.lumen_above_owner](../CellsProofs/Tissue/MembraneTrafficking.lean#L34)

Direct proof subject `cells.operator.cell_owned_compartments@1`

Uses [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** Two cells and their private lumens balanced every species against the corresponding bath within 4.34 × 10⁻¹⁹ fmol. The trafficking lumen reached +29.83 mV relative to its owner at the end of retrieval. The largest discrepancy from charge divided by capacitance across both lumens was 1.39 × 10⁻¹⁷ V.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kir2p1_mh2@1`, `cells.nav1p2_m3h_regularized@1`

**Operators** `cells.cell_owned_compartments@1`, `cells.scheduled_membrane_trafficking@1`, `cells.membrane_entity_state@1`

[Owner, bounding membrane and storage slots](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/compartments.py#L605) · [Lumen charge under a single bounding membrane](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/compartments.py#L370) · [Carrier transfer at the two outside nodes](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_trafficking.py#L665) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/checks/compartment_trafficking.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/PROGRESS.md#owned-compartment-inventory)

[Tested engine b30e3298523e](https://github.com/Eidosoma/Cells/commit/b30e3298523e49bd6c33bba01aa11561f8fba449) · [Evidence checkpoint bad3c2a2f8b6](https://github.com/Eidosoma/Cells/commit/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5)

## Biological evidence

**Open.** Lumen voltage relative to its own cytosol, with whole-compartment free charge and capacitance in the same preparation.

**Unit** mV, C, F

### matamala2021_lysosome_voltage@1

Intact HEK293 cells. The experimental convention is lumen minus cytosol. The Cells bounding patch uses the opposite orientation. Resting lysosome measurements in Fig. 4i and the optical calibration in Fig. 4. [Matamala et al. (2021), Fig. 4i](https://doi.org/10.1038/s42003-021-01916-6)

- **Evidence role** descriptive

Mean ± SD across seven independent experiments with 106 lysosome regions. The calibration estimates its zero-potential endpoint.

Resting lumen potential was +56 ± 7 mV relative to cytosol. This locates the resting voltage in this preparation. The experiment supplies neither net free charge nor capacitance, and the checked generic lumen has no calibrated native transport. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#owned-compartment-inventory)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
