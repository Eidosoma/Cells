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

**Not assessable.** How much peak outward potassium current remains at 0 mV when external pH falls from 7.3 to 6.8, given the separately normalized peak-tail activation curves.

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

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
