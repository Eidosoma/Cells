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

**Checked.** With equal maximal scales, stored effective openings from Figure 1F gave 0.72131 for the ratios at 0 mV and −90 mV on NumPy and compiled JAX CPU. Halving the acid maximum gave 0.36066. The native channel gave a peak ratio of 1.000 under both pH labels. Applying the +11.7 mV shift to its −6.0 mV midpoint gave 0.40493. Supplying both measured midpoints with native kinetics gave 0.69537. With explicitly varied free extracellular H, native tail curves give zero pH-induced shift in two independent protocols.

**Engine** `resolved_pump_tissue@3`, `cells.kv1p5_mh@1`

[Clamped population current at a declared voltage](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Kv1.5 activation, inactivation and opening](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/channels/kv1p5_mh.py#L25) · [Exponential gate update over the pulse](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/numerics/exponential_gates.py#L44) · [Held control schedule](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/definitions/surface_pump_v3_spec.py#L765) · [Tissue membrane and ionic reservoirs](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/tests/unit/test_chloride_leak_law.py#L37) · [Channel population fixture](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/validation/tissue/surface_pump_v3_fixtures.py#L61) · [Trapani and Korn, protocols, normalized openings and measured current](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/trapani2003_kv15_ph.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/kv15_ph.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#kv15-ph-activation)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `cells.kv1p5_mh@1`, `cells.passive_constant_field_permeation@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.population_unit_turnover@1`, `cells.membrane_entity_state@1`

[Kv1.5 activation and inactivation](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/channels/kv1p5_mh.py#L25) · [Clamped population current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Gate advance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/numerics/exponential_gates.py#L44) · [Constant-field ion flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/constant_field_permeation.py#L59) · [Inward rectifier slope](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Native cohort removal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/population_unit_turnover.py#L958) · [Surface population counts](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/membrane_state.py#L152) · [Two-population fixture](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/validation/fr7/unit_turnover_fixtures.py#L68) · [Paired measurements and protocols](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_replay_measurements.json) · [Kv1.5 dose and rectifier data](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Activation curve and step current](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/trapani2003_kv15_ph.json) · [Published receptor component fits](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/membrane_physiology_pairs.json) · [Red-cell chloride measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/freedman1997_chloride.json) · [Planar-bilayer potassium currents](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pfeffermann2026_potassium.json) · [Prepared clamp and pH rows](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/kv15_ph.py) · [Permeability calibration](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/charged_permeation.py) · [Population declaration and binding](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/population_units.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_law_replays.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Mixed.** Peak outward current remaining at 0 mV after acidification, the activation midpoint and the effect of extracellular potassium on current at strong depolarization.

- [Extracellular acidification shifts human Kv1.5 activation toward more positive voltages.](../WET_LAB_EVIDENCE.md#pair-kv15-acid-activation-shift) · Supported by both studies
- [Higher external potassium reduces the suppression of Kv1.5 current by extracellular acidification at strong depolarization.](../WET_LAB_EVIDENCE.md#pair-kv15-potassium-protection) · Supported by both studies
- [Low external potassium strengthens acid suppression of wild-type human Kv1.5.](../WET_LAB_EVIDENCE.md#pair-kv15-acid-potassium-interaction) · Supported by both studies

Measured activation curves from one preparation predict its separate 0 mV pulse approximately. In the registered voltage-only gate, changing extracellular H produces zero midpoint shift. Independent experiments resolve a positive shift and potassium-dependent suppression of current. The +100 mV protocol exceeds the gate’s declared voltage range.

**Unit** fraction of control current

### trapani2003_kv15_ph

Wild-type human Kv1.5 expressed in HEK293 cells, whole-cell at room temperature, 100 mM internal and 10 mM external K⁺. Figure 1F uses voltage-dependent prepulse durations and peak tails at −90 mV. Figure 1B compares outward currents in a pulse from −80 to 0 mV. Figure 1F at the 0 mV prepulse and the activation midpoints in its caption. Figure 1B’s 75 ms current was held out from fitting and scored in the 21 November replay. [Trapani and Korn (2003), Fig. 1B and 1F](https://doi.org/10.1016/S0006-3495(03)74842-5)

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

At pH 7.4 and 6.5 the midpoint was −14.2 ± 2.1 and +3.1 ± 0.7 mV. The dominant activation time constant at +60 mV also increased from 2.10 ± 0.20 to 4.23 ± 0.30 ms. Separately normalized curves leave the absolute conductance scale open. The fast and slow tail-decay components are separate published readouts available for a future comparison. [FR-63 source audit](../PROGRESS.md#fr63-holdout-audit) [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

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

### jager2001_kv15_potassium@1

Wild-type human Kv1.5 recorded at +40 mV at two external K concentrations and two pH values. Fig. 2, wild-type human Kv1.5 peak outward current in RBL cells. [Jäger et al. (2001), Fig. 2](https://doi.org/10.1016/S0014-5793(00)02396-6)

- **Evidence role** descriptive

Approximate ratios within each pH condition. Authors describe the normal-pH peaks as similar. No group error or sample count given for these ratios. Intracellular free K was not measured. The pipette was titrated with KOH to pH 7.2.

At pH 7.4 the peak currents at nominal zero and 4.5 mM K were similar. At pH 6.0 the zero-K current was about one tenth of the 4.5 mM value. The current example supplies an in-range test of the interaction. [Dataset manifest](../checks/data/paired_replay_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-law-replays)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
