<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Chloride gradients set leak reversal and inward chloride carries positive outward current

For the gate-free Cl⁻ population, outward material flux J produces outward electrical current −F × 10⁻¹⁵ × J amperes for J in fmol/s. The conducting route reverses at V = (RT/F) × (ln inside − ln outside) on the regular Bernoulli branch and at zero voltage. On the small nonzero branch its reversal follows the implemented polynomial ratio.

## Assumptions

- Voltage is inside minus outside. Concentrations, absolute temperature, F and RT are positive. Permeability, area, abundance and availability give a positive scale for the reversal claim.
- The formal calculation is over real numbers. The regular branch uses |FV/(RT)| ≥ 10⁻⁴. The sign conversion applies to either flux branch. In the tissue comparison, a single membrane connects the cell to a grounded bath and the chloride population is the only conductive route.

## Lean proof

**Proved**

- [CellsProofs.Transport.IonChannels.chloride_flux](../CellsProofs/Transport/IonChannels.lean#L160)
- [CellsProofs.Transport.IonChannels.chloride_reversal_iff](../CellsProofs/Transport/IonChannels.lean#L168)
- [CellsProofs.Transport.IonChannels.chloride_current_positive_iff](../CellsProofs/Transport/IonChannels.lean#L183)
- [CellsProofs.Transport.IonChannels.other_flux](../CellsProofs/Transport/IonChannels.lean#L202)
- [CellsProofs.Transport.IonChannels.patch_booking](../CellsProofs/Transport/IonChannels.lean#L211)

Direct proof subject `cells.clleak_always_open@1`

Uses [Voltage and free proton concentrations set the leak reversal](proton-leak.md) · [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** At the same initial voltage, 147 and 70 mM bath chloride gave opposite fluxes and initial electrode currents of +0.573 and −5.733 pA. The two tissue trajectories matched an independent solution within 1.58 × 10⁻¹² fmol of transfer, with zero off-ion and padding flux.

**Engine** `resolved_pump_tissue@3`, `clleak_always_open@1`

[Chloride population and valence](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/channels/clleak_always_open.py#L20) · [Outward population flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L370) · [Membrane and held-electrode currents](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L938) · [Cell, bath and chloride substitution](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_chloride_leak_law.py#L37) · [Independent constant-field calculation](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_transport/check.py#L10) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/chloride_channel.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Open.** Shift in the single-channel reversal potential when the nominal extracellular chloride concentration changes at fixed intracellular chloride and temperature.

- [Lowering extracellular chloride shifts the reversal of a chloride-selective epithelial current in the positive direction.](../WET_LAB_EVIDENCE.md#pair-epithelial-chloride-gradient) · Supported by both studies

**Unit** mV

### bajnath1993_chloride_reversal@1

Forskolin-stimulated, cell-attached patches of human HT-29cl.19A epithelium at 25 °C. Pipette chloride was lowered with osmotic compensation. Methods, Fig. 2 and accompanying Results, closed-to-open single-channel amplitudes. [Bajnath et al. (1993), Fig. 2](https://doi.org/10.1007/BF00374509)

- **Evidence role** descriptive

The high-chloride reversal was 2 ± 1 mV on the −Vₚ scale. The low-chloride endpoint was about 25 mV. No error on their difference was reported.

Lowering external chloride shifted the reversal positive. Cells gives +24.86 mV at 25 °C for a fixed internal chloride concentration. The inside-out control at symmetric chloride was a separate experiment. [Dataset manifest](../checks/data/paired_transport_responses.json) · [Comparison verdict](../PROGRESS.md#paired-transport-and-membrane-measurements)

### Ling 1994 chloride substitution

Cell-attached apical patches of cultured rabbit collecting-tubule principal cells at 37 °C. Pipette chloride was lowered from 145 to 15 mM by partial substitution with gluconate. The voltage scale is relative to the resting membrane potential. Figure 1B and accompanying Results. [Ling et al., Fig. 1B](https://doi.org/10.1172/JCI117037)

- **Evidence role** descriptive
- **Observed** 45 mV
- **Predicted** 60.6 mV

The two conditions used 11 and 4 patches, with no endpoint uncertainty reported.

The measured shift is approximate. Lowering nominal outside chloride from 145 to 15 mM in rabbit kidney patches at 37 °C shifted reversal in the predicted positive direction. The channels also passed bromide and showed regulated opening. Absolute permeability remains uncalibrated. [Dataset manifest](incoming/channel-gating-evidence.md#chloride-leak) · [Comparison verdict](../PROGRESS.md#19-november-2026--chloride-leak)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
