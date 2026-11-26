<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# At fixed channel drive, whole-patch flow tracks the surface unit count

The membrane state converts declared abundance and a signed unit change to a density at the current patch area. Multiplication by area cancels that dilution, so total channel flow scales with the surface unit count at fixed single-channel drive.

## Assumptions

- Patch area and reference density are positive. Capacitance, voltage, concentration difference, permeability and gating are fixed for the flow comparison.
- The endplate comparison assumes that available binding-site density is proportional to available functional units across conditions, with comparable effective areas and per-unit driving conditions.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PopulationUnits.abundance_from_units](../CellsProofs/Chemistry/PopulationUnits.lean#L126)
- [CellsProofs.Chemistry.PopulationUnits.whole_patch_flow](../CellsProofs/Chemistry/PopulationUnits.lean#L135)

Direct proof subject `cells.operator.membrane_entity_state@1`

Uses [Channel opening scales the signed transfer of sodium or potassium](channel-ion-transfer.md)

## Numerical comparison

**Checked.** At 1, 1.4 and 1.8 times the declared area, two populations on one patch preserved their potassium fluxes at fixed count. Halving each count halved its flux. The largest relative difference was 4.45 × 10⁻¹⁶ across NumPy and compiled CPU controls.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.membrane_entity_state@1`

[Surface unit count and relative abundance](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L151) · [Area and abundance passed to the engine](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L236) · [Whole-patch channel rates](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/models/surface_pump_v3.py#L360) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#membrane-population-flow)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

## Biological evidence

**Open.** Peak synaptic-current magnitude at measured available receptor-site densities and whole-patch flow at fixed count as surface area changes.

- [Within each preparation, fewer available postsynaptic acetylcholine-receptor binding sites accompany a smaller miniature endplate current.](../WET_LAB_EVIDENCE.md#pair-receptor-sites-and-current) · Supported by both studies

Two preparations link a smaller receptor binding-site count or density to a smaller miniature endplate current. Exact proportionality at fixed unit drive and the effect of changing area at fixed count remain open.

**Unit** nA

### land1980_receptor_sites_and_current@1

Esterase-inactivated lizard intercostal endplates were recorded at −100 mV and 23 °C. Density is per µm² of receptor-rich membrane. Table 1 reports available receptor-site densities and absolute miniature endplate current amplitudes for three conditions. [Land et al. (1980), Table 1](https://doi.org/10.1073/pnas.77.6.3736)

- **Evidence role** held out from fitting
- **Fit** Control with 18,000 sites/µm² and 7.5 nA mean peak current
- **Evaluation** 8,200 sites/µm², 6,900 sites/µm²

Estimated standard errors include systematic uncertainties in current and density. The table gives condition means without a biological sample count per row.

Scaling by central density gave 3.42 and 2.88 nA against 4.0 ± 0.7 and 2.5 ± 0.5 nA. Both values are within the reported current uncertainties. The measurements leave the functional unit count and the effect of varying area at fixed count open. [Dataset manifest](../checks/data/surface_population_measurements.json) · [Comparison verdict](../PROGRESS.md#membrane-population-flow)

### ohno2002_achr_count_current@1

Human intercostal endplates. A receptor-scaffold deficiency reduced available binding sites. Miniature endplate currents were recorded at −80 mV and 22 ± 0.5 °C. Table 2 and footnotes. Patient 3 and controls for the adult comparison [Ohno et al. (2002), Table 2, patient 3 and controls](https://doi.org/10.1086/339465)

- **Evidence role** descriptive

Table reports SE. No error or replicate count for this patient’s binding-site estimate. The measurements were not linked by individual endplate. Endplate geometry, local opening and transmitter exposure could differ. Patient 4 was a child and has no age-matched site count in the table.

The adult patient had 5.7 million binding sites per endplate and a 1.83 ± 0.15 nA mean current. Controls had 12.82 ± 0.79 million sites and 3.95 ± 0.10 nA. The patient retained 44.5% of the adult mean sites and 46.3% of control current. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
