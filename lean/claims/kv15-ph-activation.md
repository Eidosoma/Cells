<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Kv1.5 activation and current retention under extracellular acidification

With common nonzero ionic drive, the treated/control current ratio is the product of the fully open population-scale ratio and the effective-opening ratio. For a rising Boltzmann curve of fixed positive width, translating the midpoint to the right makes the treated/control activation ratio increase strictly with voltage.

## Assumptions

- The control has positive maximal scale and opening. Both conditions share the single-open-channel drive at the test voltage, including permeant ion, temperature and concentrations.
- Transferring the separately normalized peak tails in Figure 1F to the Figure 1B current assumes equal absolute maximal conductance and comparable peak openings in both protocols. Figure 1B supplies no input to the prediction.
- The registered-channel sensitivity calculation moves only the activation midpoint. Inactivation, both gate time scales, channel count, permeability, ionic drive and the registered activation slope stay fixed.

## Lean proof

**Proved**

- [CellsProofs.Transport.IonChannels.clamp_ratio_from_openings](../CellsProofs/Transport/IonChannels.lean#L298)
- [CellsProofs.Transport.IonChannels.right_shift_ratio_strictMono](../CellsProofs/Transport/IonChannels.lean#L311)

Proof sources [Mathlib cancellation of the common nonzero drive](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L317-L325) · [Mathlib strict monotonicity of the real exponential](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Complex/Exponential.lean#L288-L295)

Uses [A fixed-gate current curve identifies the product of channel abundance and availability](clamped-channel-current.md) · [Independent channel counts determine relative availability from fixed-gate currents](channel-density-availability.md) · [Voltage-gated channel openings stay between zero and one](channel-gate-bounds.md)

## Numerical comparison

**Checked.** With equal maximal scales, stored effective openings from Figure 1F gave 0.72131 for the ratios at 0 mV and −90 mV on NumPy and compiled JAX CPU. Halving the acid maximum gave 0.36066. The native channel gave a peak ratio of 1.000 under both pH labels. Applying the +11.7 mV shift to its −6.0 mV midpoint gave 0.40493. Supplying both measured midpoints with native kinetics gave 0.69537.

**Engine** `resolved_pump_tissue@3`, `cells.kv1p5_mh@1`

[Clamped population current at a declared voltage](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L415) · [Kv1.5 activation, inactivation and opening](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/channels/kv1p5_mh.py#L25) · [Exponential gate update over the pulse](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/numerics/exponential_gates.py#L44) · [Held control schedule](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/definitions/surface_pump_v3_spec.py#L563) · [Tissue membrane and ionic reservoirs](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_chloride_leak_law.py#L37) · [Channel population fixture](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/surface_pump_v3_fixtures.py#L61) · [Trapani and Korn, protocols, normalized openings and measured current](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/data/trapani2003_kv15_ph.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/kv15_ph.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#kv15-ph-activation)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Not assessable.** Peak outward current remaining at 0 mV after acidification, the activation midpoint and the effect of extracellular potassium on current at strong depolarization.

- [Extracellular acidification shifts human Kv1.5 activation toward more positive voltages.](../WET_LAB_EVIDENCE.md#pair-kv15-acid-activation-shift) · Supported by both studies
- [Higher external potassium reduces the suppression of Kv1.5 current by extracellular acidification at strong depolarization.](../WET_LAB_EVIDENCE.md#pair-kv15-potassium-protection) · Supported by both studies

Independent human Kv1.5 recordings support a positive shift in activation voltage with acidification and less acid-induced current suppression at higher external potassium. The absolute 0 mV response still depends on activation kinetics and the available conductance in the pulse protocol.

**Unit** fraction of control current

### trapani2003_kv15_ph

Wild-type human Kv1.5 expressed in HEK293 cells, whole-cell at room temperature, 100 mM internal and 10 mM external K⁺. Figure 1F uses voltage-dependent prepulse durations and peak tails at −90 mV. Figure 1B compares outward currents in a pulse from −80 to 0 mV. Figure 1F at the 0 mV prepulse and the activation midpoints in its caption. The 75 ms step in Figure 1B is held out. [Trapani and Korn (2003), Fig. 1B and 1F](https://doi.org/10.1016/S0006-3495(03)74842-5)

- **Evidence role** held out from fitting
- **Fit** Figure 1F peak-tail fractions at 0 mV and the two activation midpoints
- **Evaluation** Figure 1B 0 mV step-current ratio at pH 6.8 versus 7.3
- **Observed** 0.745 fraction of control current
- **Predicted** 0.72131 fraction of control current

Figure 1B reports SEM 0.019 over eight cells. Figure 1F normalizes each condition separately and gives neither the absolute maxima nor enough information to propagate experimental uncertainty. Reading both plotted fractions within ±0.01 gives 0.703–0.740 from graph precision alone. Both assays come from one study.

The equal-maximum projection is 0.0237 below the measured fraction. The control midpoint explains why imposing the measured shift on the default Cells gate gives a smaller ratio. Quantitative pH validation needs comparable maximum conductances and matched activation kinetics. [Dataset manifest](../checks/data/trapani2003_kv15_ph.json) · [Comparison verdict](../PROGRESS.md#kv15-ph-activation)

### longobardo2001_kv15_controls@1

Wild-type human Kv1.5 in Ltk− cells, whole-cell clamp, 4 mM extracellular K, 21–23 °C. The tail voltage changed from −40 to −30 mV between pH conditions. Figure 1 and drug-free control results [Longobardo et al. (2001), Fig. 1 and control results](https://doi.org/10.1038/sj.bjp.0704251)

- **Evidence role** descriptive

Mean ± SEM. Midpoint groups included 38 control and 27 acidic recordings. Tail voltages differed by 10 mV between conditions.

At pH 7.4 and 6.5 the midpoint was −14.2 ± 2.1 and +3.1 ± 0.7 mV. The dominant activation time constant at +60 mV also increased from 2.10 ± 0.20 to 4.23 ± 0.30 ms. Separately normalized curves leave the absolute conductance scale open. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### trapani2003_kv15_high_voltage@1

Wild-type human Kv1.5 in HEK293. Same study as the existing 0 mV pulse and activation curves. Figures 1C/D and 9B, +100 mV [Trapani and Korn (2003), Figs. 1C/D and 9B](https://doi.org/10.1016/S0006-3495(03)74842-5)

- **Evidence role** descriptive

At 0 and 3 mM external K, reported errors are SEM, n = 3 each. At 10 mM the text gives a qualitative group result, n = 5.

For the same pH change and 10 mM external K as the 0 mV comparison, the current at +100 mV was essentially unchanged. At zero external K only 38.0 ± 1.5% remained. This constrains the maximal-current interpretation at strong depolarization. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### kehl2002_kv15_potassium@1

WT human Kv1.5 in HEK293, 20–25 °C, whole-cell tails after 300-ms prepulses. Figure 2 and Results, external potassium and the conductance response [Kehl et al. (2002), Fig. 2](https://doi.org/10.1113/jphysiol.2001.014456)

- **Evidence role** descriptive

Reported ± as printed. Methods generally use SEM and specify SD for nonlinear least-squares outputs.

At 0, 3.5 and 140 mM extracellular K, acid/control maximum conductance was 0.19 ± 0.02, 0.56 ± 0.01 and 0.81 ± 0.12 (n = 12, 6, 6). At 3.5 mM K the activation midpoint also shifted by +7.8 mV. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
