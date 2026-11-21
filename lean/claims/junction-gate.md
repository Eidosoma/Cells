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

[Voltage dependence and constant-voltage update](https://github.com/Eidosoma/Cells/blob/6d74998581eab13d45327bc4801b463d0fb7a6f7/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Tissue transport opening](https://github.com/Eidosoma/Cells/blob/6d74998581eab13d45327bc4801b463d0fb7a6f7/src/cells/models/surface_pump_v3.py#L733) · [Intrinsic gate rate in the tissue](https://github.com/Eidosoma/Cells/blob/6d74998581eab13d45327bc4801b463d0fb7a6f7/src/cells/models/surface_pump_v3.py#L779) · [Independent voltage-clamp protocol](https://github.com/Eidosoma/Cells/blob/6d74998581eab13d45327bc4801b463d0fb7a6f7/validation/betse/junction_gate/protocol.json) · [Independent rate calculation in mV and ms](https://github.com/Eidosoma/Cells/blob/6d74998581eab13d45327bc4801b463d0fb7a6f7/validation/betse/junction_gate/reference.py#L9) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/394a9294379f7636b7f75993fee850363c04bd26/lean/checks/junction_gate.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/394a9294379f7636b7f75993fee850363c04bd26/lean/PROGRESS.md#19-november-2026--voltage-gated-junction-conductance)

[Tested engine 6d74998581ea](https://github.com/Eidosoma/Cells/commit/6d74998581eab13d45327bc4801b463d0fb7a6f7) · [Evidence checkpoint 394a9294379f](https://github.com/Eidosoma/Cells/commit/394a9294379f7636b7f75993fee850363c04bd26)

**Engine** `resolved_pump_tissue@3`, `cells.junction_voltage_relaxation@1`

[Intrinsic gate kinetics and clamp solution](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Tissue junction transport and gate dynamics](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/models/surface_pump_v3.py#L733) · [Voltage-clamp protocol](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/betse/junction_gate/protocol.json) · [Independent clamp solution](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/betse/junction_gate/reference.py#L9) · [Cell-pair fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/tissue/surface_pump_v3_fixtures.py) · [Published Cx43 fit parameters](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/data/revilla1999_cx43.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/junction_gate.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#cx43-series-gates)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Normalized junction conductance at each clamp polarity and the number and duration of decay components during a fixed-voltage step.

Seven wild-type Cx43 cell pairs gave residual conductances of 0.35 ± 0.01 and 0.33 ± 0.01 relative to the prepulse at positive and negative voltages. At −100 mV the same decay had two time constants, 70 ± 5 and 931 ± 54 ms (SEM). The Cells reference parameters give one time constant of 50.0 ms. An independent wild-type Cx43 series in N2a pairs reported fast and slow times of 0.25 ± 0.04 and 3.18 ± 0.12 s at 60 mV. The experiments leave exact transient polarity symmetry and the independent availability multiplier open. [Sahu and Bera, Table 2 and Fig. S2](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607587/) · [Moreno et al., Fig. 5A and Table 2](https://doi.org/10.1161/hh0402.105667)

**Unit** dimensionless normalized conductance and ms

### revilla1999_cx43_polarity@1

Homotypic wild-type rat Cx43 in paired Xenopus oocytes, with conductance normalized to a 10 mV prepulse. Table 1, RCx43–RCx43 row, and Fig. 3C. [Revilla, Castro and Barrio (1999)](https://doi.org/10.1016/S0006-3495(99)76986-9)

- **Evidence role** descriptive

Table 1 reports rounded parameters for both fitted curves. Uncertainties for those parameters and their covariance are unavailable.

At −80 and +80 mV the published fits give 0.48745 and 0.38171. A model predicting the same value at both voltages must miss at least one fit by 0.05287 in normalized conductance (rounded). A significance test on paired observations remains open. [Dataset manifest](../checks/data/revilla1999_cx43.json) · [Comparison verdict](../PROGRESS.md#cx43-series-gates)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
