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

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_constant_field_leak@1`, `cells.inward_rectifier_linear_driving_force@1`, `cells.kir2p1_mh2@1`, `cells.rapid_binding@1`

[Tight-coupled proton pump](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/pumps/proton_pump.py#L91) · [Proton flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/transport/proton_leak.py#L31) · [Kir slope conductance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Two binding forms](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/reactions/rapid_binding.py#L340) · [Tissue channel current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Preparation records](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_preparation_controls.json) · [Kir slopes and controls](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_replay_measurements.json) · [Fixed-drive Kir evaluation](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_law_replays.py) · [Native proton roots](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_membrane_physiology.py) · [Tissue clamp specimen](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/clamped_channel_current.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_preparation_controls.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/PROGRESS.md#preparation-evidence-review)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 01edbd968e18](https://github.com/Eidosoma/Cells/commit/01edbd968e182f91c0bd281fe776f5609a78e645)

## Biological evidence

**Open.** Ion-specific flux or current at known driving force, with an independently measured availability or single-channel open fraction.

- [A single tetravalent blocker moving through at most the full electric field can account for the steep component of Kir2.1 spermine block.](../WET_LAB_EVIDENCE.md#pair-kir-spermine-steep-valence) · Challenged by both studies

At −60 mV, 100 µM cytoplasmic spermine reduced the Kir2.1 single-channel current magnitude from 2.00 ± 0.04 to 1.40 ± 0.04 pA with no significant change in open probability. A voltage-only gate misses that change in unitary conductance. The two generic leak laws have no assigned molecular isoform or preparation-specific permeability. [Xie et al., Figs. 1–3](https://doi.org/10.1085/jgp.20028576)

**Unit** fmol/s or pA with the ion charge identified

### ishihara2004_spermine

Kir2.1 in excised HEK-cell patches at 24–26 °C, high symmetric K, intracellular spermine. Fig. 3A,C and Eq. 4. [Ishihara and Ehara (2004)](https://doi.org/10.1113/jphysiol.2003.055434)

- **Evidence role** descriptive

4.8 mV is the fitted e-fold scale of high-affinity Kd versus voltage. The paper gives no separate uncertainty for this fit.

This corresponds to apparent valence 5.33–5.37. The local half-block slope of total current is a different observable. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### panama2006_spermine

Excised Kir2.1 patches in symmetric high K. A two-component fit was made to blocked-to-free relative current with 300 µM intracellular spermine. Fig. 1 and Table 1. [Panama and Lopatin (2006)](https://doi.org/10.1113/jphysiol.2005.097741)

- **Evidence role** descriptive

Mean ± SEM across seven patches. The estimate depends on separating shallow and steep components.

The steep component gave an effective valence of 5.0 ± 0.2. This corresponds to 5.17 mV per e-fold at the fit temperature of 300 K. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### lopatin1996_k_asymmetry

Kir2.1 expressed in oocytes. Internal and external K were varied separately during polyamine block. Figs. 2–3 and reversal-shift analysis. [Lopatin and Nichols (1996)](https://doi.org/10.1085/jgp.108.2.105)

- **Evidence role** descriptive

The shift ratios are fitted relationships in this preparation. Lopatin also coauthored the 2006 study.

At 20 µM spermine the shift in rectification per change in K reversal was +0.91 for external K and −0.15 for internal K. A universal V−E offset would give +1 for both. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
