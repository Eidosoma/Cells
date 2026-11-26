<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Channel opening scales the signed transfer of sodium or potassium

The seven gated K⁺ laws, one gated Na⁺ law and two single-ion leaks multiply the fully open constant-field flux by their opening and external availability. The opening is m h² for Kv1.1 and Kir2.1, m h for Kv1.2–Kv1.6, m³ h for NaV1.2 and one for the two leaks. With availability between zero and one the magnitude cannot exceed the fully open flux. Blocking gives zero. Only the declared ion crosses, debiting the cell and crediting the exterior. With a block fraction determined by V − E at fixed dose, matched driving voltages give equal blocked/free current ratios wherever the free currents are nonzero.

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
- [CellsProofs.Transport.IonChannels.relative_block_at_equal_drive](../CellsProofs/Transport/IonChannels.lean#L333)

Direct proof subject `cells.channel.kv1p1_mh2@1`, `cells.channel.kv1p2_mh@1`, `cells.channel.kv1p3_mh@1`, `cells.channel.kv1p4_mh@1`, `cells.channel.kv1p5_mh@1`, `cells.channel.kv1p6_mh@1`, `cells.channel.kir2p1_mh2@1`, `cells.channel.nav1p2_m3h_regularized@1`, `cells.channel.kleak_always_open@1`, `cells.channel.naleak_always_open@1`

Proof sources [Imported Mathlib cancellation of a shared voltage offset](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Group/Defs.lean#L1104) · [Imported Mathlib cancellation of a nonzero free current](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Defs.lean#L178)

Uses [Voltage-gated channel openings stay between zero and one](channel-gate-bounds.md) · [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** All ten populations shared one membrane. Potassium moved out and sodium moved in after release. Every off-ion and padding transfer was zero. The largest per-channel cumulative discrepancy was 2.37 × 10⁻¹³ fmol against an independent adaptive solution.

**Engine** `resolved_pump_tissue@3`, `kv1p1_mh2@1`, `kv1p2_mh@1`, `kv1p3_mh@1`, `kv1p4_mh@1`, `kv1p5_mh@1`, `kv1p6_mh@1`, `kir2p1_mh2@1`, `nav1p2_m3h_regularized@1`, `kleak_always_open@1`, `naleak_always_open@1`

[Tissue channel kinetics and opening](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L316) · [Tissue outward per-ion flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L370) · [Exponential stage and its small-step series](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/numerics/exponential_gates.py#L36) · [Gate update in the tissue integrator](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L1689) · [Per-channel transfer and membrane balance](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L2839) · [Independent Kv1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kv1_reference.py#L13) · [Independent Kir2.1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kir_reference.py#L10) · [Independent NaV1.2 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/sodium_reference.py#L12) · [Independent constant-field flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_transport/check.py#L10) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/ion_channels.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_constant_field_leak@1`, `cells.inward_rectifier_linear_driving_force@1`, `cells.kir2p1_mh2@1`, `cells.rapid_binding@1`

[Tight-coupled proton pump](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/pumps/proton_pump.py#L91) · [Proton flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/transport/proton_leak.py#L31) · [Kir slope conductance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Two binding forms](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/reactions/rapid_binding.py#L340) · [Tissue channel current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Preparation records](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_preparation_controls.json) · [Kir slopes and controls](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_replay_measurements.json) · [Fixed-drive Kir evaluation](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_law_replays.py) · [Native proton roots](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_membrane_physiology.py) · [Tissue clamp specimen](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/clamped_channel_current.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_preparation_controls.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/PROGRESS.md#preparation-evidence-review)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 01edbd968e18](https://github.com/Eidosoma/Cells/commit/01edbd968e182f91c0bd281fe776f5609a78e645)

**Engine** `resolved_pump_tissue@3`, `cells.kir2p1_mh2@1`, `open_channel_block_weighted_modes@1`

[FR-51 development block and reversal](https://github.com/Eidosoma/Cells/blob/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31/src/cells/laws/channels/open_channel_block.py#L55) · [Native current clamp](https://github.com/Eidosoma/Cells/blob/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31/src/cells/models/surface_pump_v3.py#L847) · [Validation world template](https://github.com/Eidosoma/Cells/blob/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31/validation/fr51/engine.py#L98) · [Template case declaration](https://github.com/Eidosoma/Cells/blob/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31/validation/fr51/references/spec/cases.json) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31/src/cells/laws/electrochemistry.py#L10) · [Potassium levels, graph readings and assay scope](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/checks/data/kir_spermine_potassium.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/checks/kir_spermine_potassium.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/PROGRESS.md#fr51-two-potassium)

[Tested engine 7ca7c9c15f7f](https://github.com/Eidosoma/Cells/commit/7ca7c9c15f7f02983aeb103b989c5d0a739e9d31) · [Evidence checkpoint 369431f74ae5](https://github.com/Eidosoma/Cells/commit/369431f74ae5108c8be47f3a0afc80623de7f028)

## Biological evidence

**Open.** Ion-specific flux or current at known driving force, with an independently measured availability or single-channel open fraction.

- [A single tetravalent blocker moving through at most the full electric field can account for the steep component of Kir2.1 spermine block.](../WET_LAB_EVIDENCE.md#pair-kir-spermine-steep-valence) · Challenged by both studies
- [With a fixed intracellular spermine dose in each preparation, changing external potassium moves the half-conductance voltage of Kir2.1 approximately with its measured potassium reversal.](../WET_LAB_EVIDENCE.md#pair-kir-spermine-external-potassium) · Supported by both studies

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

At 20 µM spermine the shift in rectification per change in K reversal was +0.91 for external K and −0.15 for internal K. A universal V−E offset would give +1 for both. In Fig. 3C, increasing internal K from 150 to 625 mM shifts half-block by about +5 mV while the reversal shifts about −36 mV. The native FR-51 controls predict −36.3 mV or zero. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#fr51-two-potassium)

### panama2006_external_k

Mouse Kir2.1 in HEK293 outside-out patches, 30 µM total and about 7 µM free spermine. Fig. 3A and E supply approximate reversals and relative-current curves. [Panama and Lopatin (2006), Figs. 3A,E,F and Table 2](https://doi.org/10.1113/jphysiol.2005.097741)

- **Evidence role** held out from fitting
- **Fit** 5.4 mM external K, training curve
- **Evaluation** 60 mM external K, no refit

Representative curves lack pointwise errors. The unblocked current was extrapolated and matching of the example panels to one patch is unspecified.

Half of the total normalized conductance shifted about +51.6 mV for a measured +53.2 mV reversal shift. The separate pooled steep-mode slope was 0.98 ± 0.01 across two patches. [Dataset manifest](../checks/data/kir_spermine_potassium.json) · [Comparison verdict](../PROGRESS.md#fr51-two-potassium)

### ishihara2007_external_k

Wild-type Kir2.1, HEK293T inside-out patches, 24–25 °C. Each K concentration uses different patches. Upward triangles at 1 µM, normalized to the 0.1 µM conductance maximum. [Ishihara and Yan (2007), Figs. 4 and 5A–B](https://doi.org/10.1113/jphysiol.2007.136028)

- **Evidence role** held out from fitting
- **Fit** 150 mM external K, training curve
- **Evaluation** 50 mM external K, no refit, 20 mM external K, no refit

150 mM n=5, 50 mM n=6–8 and 20 mM n=2. The 20 mM group has no reported errors. Graph reading is about 1 mV and 0.03 in conductance fraction near the transition.

The total half-conductance shifts were about −26.1 and −48.1 mV against measured reversal shifts −26.9 and −48.9 mV. The resulting ratios of about 0.97 and 0.98 use measured curve points and share a calibration. [Dataset manifest](../checks/data/kir_spermine_potassium.json) · [Comparison verdict](../PROGRESS.md#fr51-two-potassium)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
