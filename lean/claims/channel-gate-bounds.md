<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Voltage-gated channel openings stay between zero and one

For the six Kv1 laws, Kir2.1 and NaV1.2, both targets lie between zero and one and both time constants are positive on the declared voltage interval. An exponential tissue stage preserves the opening bounds when its two endpoint voltages differ. At a fixed voltage each gate’s deviation from its target decays exponentially. The whole-current response combines both gates.

## Assumptions

- Voltage is inside minus outside. Both stage endpoint voltages are between −120 and +60 mV, the elapsed time is nonnegative, and both initial gates lie in [0, 1].
- The proof uses the declared kinetics and the tissue’s exponential stage in real arithmetic, including the small-step series and both branches of the regularized sodium rates. A whole-current trace at fixed voltage and concentrations is proportional to the open fraction.

## Lean proof

**Proved**

- [CellsProofs.Transport.ChannelStep.lag_bounds](../CellsProofs/Transport/ChannelStep.lean#L23)
- [CellsProofs.Transport.ChannelStep.stage_bounds](../CellsProofs/Transport/ChannelStep.lean#L49)
- [CellsProofs.Transport.ChannelStep.clamped_residual](../CellsProofs/Transport/ChannelStep.lean#L66)
- [CellsProofs.Transport.IonChannels.stable_sigmoid](../CellsProofs/Transport/IonChannels.lean#L28)
- [CellsProofs.Transport.IonChannels.targets_bounded](../CellsProofs/Transport/IonChannels.lean#L85)
- [CellsProofs.Transport.IonChannels.times_positive](../CellsProofs/Transport/IonChannels.lean#L93)
- [CellsProofs.Transport.IonChannels.opening_bounded](../CellsProofs/Transport/IonChannels.lean#L124)
- [CellsProofs.Transport.IonChannels.stage_opening_bounded](../CellsProofs/Transport/IonChannels.lean#L140)

Direct proof subject `cells.channel.kv1p1_mh2@1`, `cells.channel.kv1p2_mh@1`, `cells.channel.kv1p3_mh@1`, `cells.channel.kv1p4_mh@1`, `cells.channel.kv1p5_mh@1`, `cells.channel.kv1p6_mh@1`, `cells.channel.kir2p1_mh2@1`, `cells.channel.nav1p2_m3h_regularized@1`

Proof sources [Mathlib exponential inequalities used in the stage proof](https://github.com/leanprover-community/mathlib4/blob/v4.19.0/Mathlib/Data/Complex/Exponential.lean#L641) · [Cells regularized Bernoulli positivity](../CellsProofs/Transport/ProtonLeak.lean#L56)

## Numerical comparison

**Checked.** The compiled dispatcher matched independent gate targets at 25 voltages within 2.23 × 10⁻¹⁶ and time constants within 1.78 × 10⁻¹⁵ s. All 72 stage cases stayed in [0, 1]. During the tissue block all eight gate pairs continued to move.

**Engine** `resolved_pump_tissue@3`, `kv1p1_mh2@1`, `kv1p2_mh@1`, `kv1p3_mh@1`, `kv1p4_mh@1`, `kv1p5_mh@1`, `kv1p6_mh@1`, `kir2p1_mh2@1`, `nav1p2_m3h_regularized@1`, `kleak_always_open@1`, `naleak_always_open@1`

[Tissue channel kinetics and opening](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L316) · [Tissue outward per-ion flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L370) · [Exponential stage and its small-step series](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/numerics/exponential_gates.py#L36) · [Gate update in the tissue integrator](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L1689) · [Per-channel transfer and membrane balance](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L2839) · [Independent Kv1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kv1_reference.py#L13) · [Independent Kir2.1 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/kir_reference.py#L10) · [Independent NaV1.2 kinetics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/sodium_reference.py#L12) · [Independent constant-field flux](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_transport/check.py#L10) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/ion_channels.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Open.** Normalized whole-current activation, decay or recovery for the same isoform, temperature, holding state and voltage-step sequence.

Rat Kv1.1 decay at −20 mV and 25 °C was 313 ± 82 ms (SD). Cells retained 88% of its peak after 1.5 s and gave a fit of about 8 s from an equilibrated −80 mV hold. Rat Kv1.4 retained under 2% after 3.2 s at 0 mV, versus 0.57% in Cells. Four gate parameters match that paper. Human NaV1.2 rose in 0.38 ± 0.05 ms (10–90%, SEM), versus 0.296 ms in Cells. Its fitted inactivation midpoint was −63.53 ± 0.79 mV, while Cells gave half of its −120 mV reference response at −54.9 mV. [Ranjan et al., Fig. 2C](https://doi.org/10.3389/fncel.2019.00358) · [Stühmer et al., Table I and Fig. 6](https://doi.org/10.1002/j.1460-2075.1989.tb08483.x) · [Begemann et al., Table 2](https://doi.org/10.1186/s10020-019-0073-6)

**Unit** normalized current, ms and mV

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
