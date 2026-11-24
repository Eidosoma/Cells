<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The eight-state sodium–anion carrier shares a cycle flux and saturates with external substrate

Each edge of a steady ring carries the same net flux. For the declared two-sodium, one-anion cycle, exact detailed balance gives the host’s thermodynamic turnover and stall. For an active population at fixed voltage, sodium and internal substrate, the increase in inward current over its zero-substrate limit has the form A x / (K + x) for positive A and K.

## Assumptions

- The carrier is at steady state on the single eight-edge ring with positive microscopic rates. Its forward and backward directions each bind the two sodium ions and the anion in the declared order. One net positive charge enters per forward cycle.
- Equality with the thermodynamic rate assumes equal products of the base rate constants and a net electrical coefficient of −1 in the forward direction. A separate theorem retains the constant and voltage residuals for populations admitted within the engine’s detailed-balance tolerance.
- The current comparison requires positive capacity and availability. The saturation result holds at fixed temperature, voltage, availability, all other activities and rate parameters. External substrate changes only its one forward binding rate. The reference current at zero substrate is the boundary value of the mass-action expression. The observed current is the measured steady current after subtracting its substrate-free baseline.

## Lean proof

**Proved**

- [CellsProofs.Transport.SodiumAnionDiagram.stationary_edge](../CellsProofs/Transport/SodiumAnionDiagram.lean#L40)
- [CellsProofs.Transport.SodiumAnionDiagram.denominator_pos](../CellsProofs/Transport/SodiumAnionDiagram.lean#L87)
- [CellsProofs.Transport.SodiumAnionDiagram.occupancy_normalized](../CellsProofs/Transport/SodiumAnionDiagram.lean#L92)
- [CellsProofs.Transport.SodiumAnionDiagram.denominator_affine](../CellsProofs/Transport/SodiumAnionDiagram.lean#L105)
- [CellsProofs.Transport.SodiumAnionDiagram.denominator_slope_pos](../CellsProofs/Transport/SodiumAnionDiagram.lean#L118)
- [CellsProofs.Transport.SodiumAnionDiagram.substrate_response](../CellsProofs/Transport/SodiumAnionDiagram.lean#L134)
- [CellsProofs.Transport.SodiumAnionDiagram.ordered_substrate_edge](../CellsProofs/Transport/SodiumAnionDiagram.lean#L178)
- [CellsProofs.Transport.SodiumAnionDiagram.ordered_dose_response](../CellsProofs/Transport/SodiumAnionDiagram.lean#L197)
- [CellsProofs.Transport.SodiumAnionDiagram.product_with_residual](../CellsProofs/Transport/SodiumAnionDiagram.lean#L221)
- [CellsProofs.Transport.SodiumAnionDiagram.cycle_flux_eq_host](../CellsProofs/Transport/SodiumAnionDiagram.lean#L231)
- [CellsProofs.Transport.SodiumAnionDiagram.cycle_stall](../CellsProofs/Transport/SodiumAnionDiagram.lean#L246)
- [CellsProofs.Transport.SodiumAnionDiagram.stall_slope](../CellsProofs/Transport/SodiumAnionDiagram.lean#L261)

Direct proof subject `cells.na2_anion_symport_diagram@1`

Uses [Sodium coupling sets net charge and the stall voltage of an anion carrier](sodium-anion-symport.md)

## Numerical comparison

**Checked.** The capacity repair passed the original controls and all four extreme/zero capacity cases on NumPy and compiled CPU. At 10⁻³⁰² fmol/s the net readouts both gave 7.09691 × 10⁻³⁰⁵ fmol/s and reverse readouts gave 2.67423 × 10⁻³⁰⁷ fmol/s. The previous 100-fold diagnostic error remains recorded at its tested revision.

**Engine** `resolved_pump_tissue@3`, `cells.na2_anion_symport_diagram@1`

[Diagnostic carrier count at normal, small and zero capacity](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/kinds/transporter.py#L2385) · [Eight-state carrier declaration](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/na2_anion_symport_diagram.py#L95) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/sodium_anion_diagram.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#sodium-anion-capacity-repair)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

**Engine** `resolved_pump_tissue@3`, `na2_anion_symport_diagram@1`

[Diagnostic carrier normalization](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/kinds/transporter.py#L2323) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/sodium_anion_diagram.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `resolved_pump_tissue@3`, `na2_anion_symport_diagram@1`

[Declared cycle and rate assignments](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/src/cells/laws/cycles/na2_anion_symport_diagram.py#L67) · [Detailed-balance check](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/src/cells/laws/cycles/forms.py#L923) · [Stationary occupancies and rates](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/src/cells/laws/cycles/forms.py#L1346) · [Capacity in the mode evaluator](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/src/cells/kinds/transporter.py#L1776) · [Capacity in the edge probe](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/src/cells/kinds/transporter.py#L2288) · [Independent 50-digit master equation](https://github.com/Eidosoma/Cells/blob/b9da010327ce52327feb86e07e76d823e2202d96/tests/unit/test_cycle_forms.py#L314) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ba3d6091cf5ac501099949b6a36a81d261c1dd72/lean/checks/sodium_anion_diagram.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ba3d6091cf5ac501099949b6a36a81d261c1dd72/lean/PROGRESS.md#20-november-2026--eight-state-sodiumanion-cotransport)

[Tested engine b9da010327ce](https://github.com/Eidosoma/Cells/commit/b9da010327ce52327feb86e07e76d823e2202d96) · [Evidence checkpoint ba3d6091cf5a](https://github.com/Eidosoma/Cells/commit/ba3d6091cf5ac501099949b6a36a81d261c1dd72)

## Biological evidence

**Open.** Baseline-subtracted steady current as external monocarboxylate concentration or clamped voltage changes. The dose series tests the functional form. A biological assignment for the individual transition rates and voltage coefficients remains open.

- [Human SMCT1 substrate-induced current saturates as external propionate increases at −50 mV.](../WET_LAB_EVIDENCE.md#pair-smct-propionate-saturation) · Supported by both studies

In an independent human SMCT oocyte series at −50 mV, the propionate half-saturation concentration was 128 ± 4 µM (SEM, n = 9). This pooled estimate constrains affinity. [Coady et al., Fig. 3A](https://doi.org/10.1113/jphysiol.2004.063859)

**Unit** nA inward magnitude (propionate), µA signed current (lactate)

### miyauchi2004_propionate@1

Human SLC5A8 in one representative Xenopus oocyte at −50 mV, 100 mM external sodium and pH 7.5. The inward current is measured relative to the substrate-free baseline. The data are the six filled symbols in the main propionate panel. [Miyauchi et al., Fig. 2A](https://doi.org/10.1074/jbc.C400059200)

- **Evidence role** held out from fitting
- **Fit** 100 µM propionate, 1,000 µM propionate
- **Evaluation** 50 µM propionate, 250 µM propionate, 500 µM propionate, 2,500 µM propionate

The approximate graph-reading precision is ±5 nA. Per-point biological uncertainties and the measurement temperature are unspecified. The paper reports similar results from three additional oocytes.

Two calibration points gave K = 130 µM. At 250 µM the proven curve predicted 260 nA against 278 nA measured. At 2,500 µM it predicted 376 nA against 371 nA. The figure provides too little biological uncertainty for a population verdict. [Dataset manifest](../checks/data/miyauchi2004_propionate.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--eight-state-sodiumanion-cotransport)

### coady2007_lactate_voltage@1

Human SMCT1 in a Xenopus oocyte, 96 mM external sodium, approximately 24 °C and pH 7.6. Subtract the substrate-free ibuprofen-sensitive trace from the 1 mM lactate trace at each negative voltage. [Coady et al., Fig. 5](https://doi.org/10.1529/biophysj.107.108555)

- **Evidence role** descriptive
- **Evaluation** −50 mV with 1 mM lactate, −150 mV with 1 mM lactate
- **Excluded** Positive-voltage currents dominated by an anion leak

One representative experiment, approximate reading precision ±0.03 µA. Intracellular activities and kinetic parameters for this preparation are unavailable.

The inward current rose from about 0.68 to 1.40 µA in magnitude between −50 and −150 mV. Predicting that voltage dependence requires the transition kinetics. [Dataset manifest](../checks/data/coady2007_lactate_voltage.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--eight-state-sodiumanion-cotransport)

### paroder2006_propionate@1

Independent human SMCT oocyte series. The same two nominal calibration doses were used on this experiment’s current scale. Filled symbols of the human propionate dose response at −50 mV. [Paroder et al. (2006), Fig. 3C](https://doi.org/10.1073/pnas.0602365103)

- **Evidence role** held out from fitting
- **Fit** 100 µM and 1,000 µM points
- **Evaluation** 50, 200, 500, 2,000 and 4,000 µM points
- **Excluded** Zero-substrate baseline, 250 µM, absent from the series
- **Observed** 22.6 nA inward magnitude (propionate), µA signed current (lactate)
- **Predicted** 22.45 nA inward magnitude (propionate), µA signed current (lactate)

The caption gives n = 3 for the kinetic analysis. Pointwise biological errors and how the symbols aggregate the recordings are unspecified. Estimated figure precision is ±0.6 nA and about ±15 µM at low dose.

At nominal 200 µM, 22.6 nA was observed and 22.45 nA predicted. The two-point fit gave half-saturation of 140.2 µM and the paper reports 162 ± 26 µM. The original 250 µM residual remains untested in this independent series. [Dataset manifest](../checks/data/paroder2006_propionate.json) · [Comparison verdict](../PROGRESS.md#smct1-independent-propionate)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
