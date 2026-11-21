<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Channel opening scales the signed transfer of sodium or potassium

The seven gated K⁺ laws, one gated Na⁺ law and two single-ion leaks multiply the fully open constant-field flux by their opening and external availability. The opening is m h² for Kv1.1 and Kir2.1, m h for Kv1.2–Kv1.6, m³ h for NaV1.2 and one for the two leaks. With availability between zero and one the magnitude cannot exceed the fully open flux. Blocking gives zero. Only the declared ion crosses, debiting the cell and crediting the exterior.

## Assumptions

- The declared population conducts K⁺ or Na⁺ with relative permeability one. The same area, permeability, abundance, voltage and concentrations define the fully open comparison. Positive flux points from the cell to the exterior.
- The gate values and external availability are in [0, 1]. The formal booking uses one cell–exterior pair. A held bath offsets the exterior credit with reservoir supply.

## Lean proof

**Proved**

- [CellsProofs.Transport.IonChannels.leak_opening](../CellsProofs/Transport/IonChannels.lean#L155)
- [CellsProofs.Transport.IonChannels.permeant_flux](../CellsProofs/Transport/IonChannels.lean#L188)
- [CellsProofs.Transport.IonChannels.flux_bound](../CellsProofs/Transport/IonChannels.lean#L193)
- [CellsProofs.Transport.IonChannels.other_flux](../CellsProofs/Transport/IonChannels.lean#L202)
- [CellsProofs.Transport.IonChannels.blocked](../CellsProofs/Transport/IonChannels.lean#L206)
- [CellsProofs.Transport.IonChannels.patch_booking](../CellsProofs/Transport/IonChannels.lean#L211)

Direct proof subject `cells.kv1p1_mh2@1`, `cells.kv1p2_mh@1`, `cells.kv1p3_mh@1`, `cells.kv1p4_mh@1`, `cells.kv1p5_mh@1`, `cells.kv1p6_mh@1`, `cells.kir2p1_mh2@1`, `cells.nav1p2_m3h_regularized@1`, `cells.kleak_always_open@1`, `cells.naleak_always_open@1`

Uses [Voltage-gated channel openings stay between zero and one](channel-gate-bounds.md) · [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** All ten populations shared one membrane. Potassium moved out and sodium moved in after release. Every off-ion and padding transfer was zero. The largest per-channel cumulative discrepancy was 2.37 × 10⁻¹³ fmol against an independent adaptive solution.

**Engine** `resolved_pump_tissue@3`, `kv1p1_mh2@1`, `kv1p2_mh@1`, `kv1p3_mh@1`, `kv1p4_mh@1`, `kv1p5_mh@1`, `kv1p6_mh@1`, `kir2p1_mh2@1`, `nav1p2_m3h_regularized@1`, `kleak_always_open@1`, `naleak_always_open@1`

[Tissue channel kinetics and opening](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L316) · [Tissue outward per-ion flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L370) · [Exponential stage and its small-step series](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/numerics/exponential_gates.py#L36) · [Gate update in the tissue integrator](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L1689) · [Per-channel transfer and membrane balance](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L2839) · [Independent Kv1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kv1_reference.py#L13) · [Independent Kir2.1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kir_reference.py#L10) · [Independent NaV1.2 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/sodium_reference.py#L12) · [Independent constant-field flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_transport/check.py#L10) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/ion_channels.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Open.** Ion-specific flux or current at known driving force, with an independently measured availability or single-channel open fraction.

At −60 mV, 100 µM cytoplasmic spermine reduced the Kir2.1 single-channel current magnitude from 2.00 ± 0.04 to 1.40 ± 0.04 pA with no significant change in open probability. A voltage-only gate misses that change in unitary conductance. The two generic leak laws have no assigned molecular isoform or preparation-specific permeability. [Xie et al., Figs. 1–3](https://doi.org/10.1085/jgp.20028576)

**Unit** fmol/s or pA with the ion charge identified

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
