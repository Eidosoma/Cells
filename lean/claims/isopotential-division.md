<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Charge carriers reconcile daughter volume and membrane shares at division

Each species balances across the daughters when charge carriers compensate for the difference between volume-weighted and area-weighted parent charge. Splitting each capacitor and its charge in the same proportion preserves patch voltage. Positive daughter amounts have nonnegative ideal unmixing cost.

## Assumptions

- Volume and active patch shares lie strictly between zero and one. Capacitors are positive. Compensating carrier charge fractions sum to one and each carrier has nonzero valence.
- Both daughters have positive amounts and proportional reference volumes. The independent work calculation uses the single-parent fixture with one membrane against a held bath.

## Lean proof

**Proved**

- [CellsProofs.Tissue.DivisionBridge.daughter_charges](../CellsProofs/Tissue/DivisionBridge.lean#L12)
- [CellsProofs.Tissue.DivisionBridge.carrier_charge](../CellsProofs/Tissue/DivisionBridge.lean#L20)
- [CellsProofs.Tissue.DivisionBridge.species_balance](../CellsProofs/Tissue/DivisionBridge.lean#L27)
- [CellsProofs.Tissue.DivisionBridge.patch_voltage](../CellsProofs/Tissue/DivisionBridge.lean#L30)
- [CellsProofs.Tissue.DivisionBridge.unmixing_nonneg](../CellsProofs/Tissue/DivisionBridge.lean#L37)

Direct proof subject `cells.operator.isopotential_partition@1`

Uses [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** For a 75% volume share and a 60% membrane share, K and counterion offsets of +0.001008 and −0.001008 fmol supplied the 1.94515 × 10⁻¹³ C mismatch. At the event, each daughter pair summed to the parent's amount exactly in float64. Daughter voltages agreed with the parent's within 1.39 × 10⁻¹⁷ V. Booked work agreed with a 65-digit unmixing calculation within 1.69 × 10⁻¹⁷ pJ.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.constant_field@1`

**Operators** `cells.isopotential_partition@1`, `cells.cytoplasmic_bridge_closure@1`, `cells.membrane_entity_state@1`

[Daughter references and shares](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/definitions/partition_spec.py#L1) · [Carrier correction and species split](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/partition.py#L879) · [Daughter potentials, chemical and capacitor work](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/partition.py#L994) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/checks/division_bridge.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/PROGRESS.md#isopotential-division)

[Tested engine b30e3298523e](https://github.com/Eidosoma/Cells/commit/b30e3298523e49bd6c33bba01aa11561f8fba449) · [Evidence checkpoint bad3c2a2f8b6](https://github.com/Eidosoma/Cells/commit/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5)

## Biological evidence

**Open.** Parent and both daughter volumes, ionic amounts, patch areas and potentials immediately across division.

**Unit** µm³, fmol, µm², mV

### xie2020_paired_epidermal_volumes@1

Eleven paired mouse basal epidermal divisions in vivo. The next image after the mitotic parent gives the sum of both daughters. Supplement p. 4, panel labelled S2L and cited as S2L in the main text. [Xie and Skotheim (2020), Fig. S2L](https://doi.org/10.1016/j.cub.2019.12.062)

- **Evidence role** descriptive

The imaging interval was 12 h. Mean repeat-segmentation difference across the study was 9.1 ± 8.6%.

The mean parent volume was 770 µm³ and the mean summed daughter volume in the next image was 677 µm³. The interval includes growth and mitotic volume changes. Instantaneous volume, carrier charge and voltage partition remain open. [Dataset manifest](../checks/data/cell_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#isopotential-division)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
