<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Junction conductance relaxes toward a voltage-dependent target

At fixed voltage the intrinsic gate approaches its target with one exponential time constant and stays between its residual conductance fraction and one. Increasing voltage magnitude lowers the target if the residual fraction is below one. Reversing polarity preserves the trajectory from the same initial state.

## Assumptions

- The junction has one intrinsic conductance state, the declared opening and closing rates, and a fixed threshold. Elapsed time is nonnegative and the initial conductance lies between the residual fraction and one.
- The tissue applies an external availability multiplier to transport. The intrinsic gate keeps evolving during a block. The time-course identity assumes constant junction voltage throughout the interval.

## Lean proof

**Proved**

- [CellsProofs.Transport.JunctionGate.target_bounds](../CellsProofs/Transport/JunctionGate.lean#L30)
- [CellsProofs.Transport.JunctionGate.target_decreases](../CellsProofs/Transport/JunctionGate.lean#L40)
- [CellsProofs.Transport.JunctionGate.rhs_eq_relaxation](../CellsProofs/Transport/JunctionGate.lean#L55)
- [CellsProofs.Transport.JunctionGate.clamp_residual](../CellsProofs/Transport/JunctionGate.lean#L62)
- [CellsProofs.Transport.JunctionGate.clamp_bounds](../CellsProofs/Transport/JunctionGate.lean#L81)
- [CellsProofs.Transport.JunctionGate.clamp_add](../CellsProofs/Transport/JunctionGate.lean#L93)
- [CellsProofs.Transport.JunctionGate.clamp_polarity](../CellsProofs/Transport/JunctionGate.lean#L98)
- [CellsProofs.Transport.JunctionGate.polarity_error_bound](../CellsProofs/Transport/JunctionGate.lean#L103)
- [CellsProofs.Transport.JunctionGate.single_decay_samples](../CellsProofs/Transport/JunctionGate.lean#L68)
- [CellsProofs.Transport.JunctionGate.two_decay_samples](../CellsProofs/Transport/JunctionGate.lean#L76)

Direct proof subject `cells.junction_voltage_relaxation@1`

## Numerical comparison

**Checked.** Across 45 constant-voltage samples the compiled gate matched the independent reference within 1.12 × 10⁻¹⁶. In three tissue cell pairs the intrinsic gates continued moving during a 31.25 ms block, and tracer transfer after release matched the integrated reference within 8.68 × 10⁻¹⁸ fmol. At −80 and +80 mV the intrinsic steady target was 0.1003927 at each polarity.

**Engine** `resolved_pump_tissue@3`, `junction_voltage_relaxation@1`

[Exponential gate stage](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L1708) · [Voltage dependence and constant-voltage update](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Tissue transport opening](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L849) · [Intrinsic gate rate in the tissue](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L895) · [Independent voltage-clamp protocol](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_gate/protocol.json) · [Independent rate calculation in mV and ms](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_gate/reference.py#L9) · [Published Cx43 fit parameters](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/data/revilla1999_cx43.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/junction_gate.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

**Engine** `resolved_pump_tissue@3`, `cells.junction_voltage_relaxation@1`

[Exponential gate stage](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L1708) · [Intrinsic gate kinetics and clamp solution](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Tissue junction transport and gate dynamics](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L849) · [Voltage-clamp protocol](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_gate/protocol.json) · [Independent clamp solution](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/junction_gate/reference.py#L9) · [Cell-pair fixture](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/tissue/surface_pump_v3_fixtures.py) · [Published Cx43 fit parameters](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/data/revilla1999_cx43.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/junction_gate.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Mixed.** Normalized junction conductance at each clamp polarity and the number and duration of decay components during a fixed-voltage step.

- [One relaxation time describes the decay of homotypic wild-type Cx43 junction current during a sustained −100 mV step.](../WET_LAB_EVIDENCE.md#pair-cx43-single-exponential-clamp) · Challenged by both studies

Seven wild-type Cx43 cell pairs gave residual conductances of 0.35 ± 0.01 and 0.33 ± 0.01 relative to the prepulse at positive and negative voltages. At −100 mV the same decay had two time constants, 70 ± 5 and 931 ± 54 ms (SEM). The Cells reference parameters give one time constant of 50.0 ms. An independent wild-type Cx43 series in N2a pairs reported fast and slow times of 0.25 ± 0.04 and 3.18 ± 0.12 s at 60 mV. The experiments leave exact transient polarity symmetry and the independent availability multiplier open. Both oocyte and N2a controls show voltage-dependent relaxation and two decay times at −100 mV. The registered single-time-constant law captures relaxation but misses the two measured phases at this voltage. [Sahu and Bera, Table 2 and Fig. S2](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607587/) · [Moreno et al., Fig. 5A and Table 2](https://doi.org/10.1161/hh0402.105667)

**Unit** dimensionless normalized conductance and ms

### revilla1999_cx43_polarity@1

Homotypic wild-type rat Cx43 in paired Xenopus oocytes, with conductance normalized to a 10 mV prepulse. Table 1, RCx43–RCx43 row, and Fig. 3C. [Revilla, Castro and Barrio (1999)](https://doi.org/10.1016/S0006-3495(99)76986-9)

- **Evidence role** descriptive

Table 1 reports rounded parameters for both fitted curves. Uncertainties for those parameters and their covariance are unavailable.

At −80 and +80 mV the published fits give 0.48745 and 0.38171. A model predicting the same value at both voltages must miss at least one fit by 0.05287 in normalized conductance (rounded). A significance test on paired observations remains open. [Dataset manifest](../checks/data/revilla1999_cx43.json) · [Comparison verdict](../PROGRESS.md#cx43-series-gates)

### revilla1999_cx43_kinetics@1

Paired Xenopus oocytes. Untagged rat Cx43 on both sides. Same publication as the registered Cx43 steady-conductance fits. Figure 3A–C and Results, wild-type rat Cx43 homotypic junctions [Revilla, Castro and Barrio (1999), Fig. 3A–B](https://doi.org/10.1016/S0006-3495(99)76986-9)

- **Evidence role** descriptive

Reported rounded ratio. The paper presents kinetic and conductance series from six pairs. No separate sampling interval for this amplitude ratio.

At −100 mV, fitted fast and slow times were 417 ± 175 ms and 7.06 ± 1.28 s. The fast-to-slow amplitude ratio was 3. The fitted model contains two decay terms. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### sahu2013_cx43_clamp@1

Homotypic Cx43 in N2a cell pairs, transjunctional step to −100 mV for kinetics. Table 2, wild-type Cx43 row, Fig. S2 and Results on current decay [Sahu and Bera (2013), Table 2 and Fig. S2](https://doi.org/10.1371/journal.pone.0060506)

- **Evidence role** descriptive

Means ± SEM for seven pairs. These are fitted time constants in a fixed-voltage clamp.

At −100 mV, fitted fast and slow times were 70 ± 5 and 931 ± 54 ms. Steady residual conductances at positive and negative voltages were 0.35 ± 0.01 and 0.33 ± 0.01 of the prepulse. The same trace requires more than one relaxation time. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
