<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Potassium rectification sets reversal, dissipation and a bound on slope conductance

On an open route the outward current changes sign at the Nernst potential and dissipates nonnegative heat. At fixed drive it scales with the square root of external concentration. The voltage derivative obeys the host’s upper bound even when the differential conductance is negative.

## Assumptions

- The route carries a monovalent cation. Concentrations, absolute temperature, reference concentration and slope parameter are positive. The gain includes nonnegative area, availability and reference conductance. Reversal and sign require positive gain.
- The derivative holds concentrations and route parameters fixed. The biological matched-drive comparison uses constant availability, rectification parameters and number of contributing channels across the potassium series.

## Lean proof

**Proved**

- [CellsProofs.Transport.InwardRectifier.reversal_shift](../CellsProofs/Transport/InwardRectifier.lean#L28)
- [CellsProofs.Transport.InwardRectifier.sqrt_scaling](../CellsProofs/Transport/InwardRectifier.lean#L35)
- [CellsProofs.Transport.InwardRectifier.matched_drive](../CellsProofs/Transport/InwardRectifier.lean#L43)
- [CellsProofs.Transport.InwardRectifier.reference_invariance](../CellsProofs/Transport/InwardRectifier.lean#L52)
- [CellsProofs.Transport.InwardRectifier.gate_bounds](../CellsProofs/Transport/InwardRectifier.lean#L59)
- [CellsProofs.Transport.InwardRectifier.gate_branches](../CellsProofs/Transport/InwardRectifier.lean#L67)
- [CellsProofs.Transport.InwardRectifier.reversal_iff](../CellsProofs/Transport/InwardRectifier.lean#L77)
- [CellsProofs.Transport.InwardRectifier.outward_iff](../CellsProofs/Transport/InwardRectifier.lean#L81)
- [CellsProofs.Transport.InwardRectifier.dissipation](../CellsProofs/Transport/InwardRectifier.lean#L85)
- [CellsProofs.Transport.InwardRectifier.current_derivative](../CellsProofs/Transport/InwardRectifier.lean#L102)
- [CellsProofs.Transport.InwardRectifier.negative_slope_iff](../CellsProofs/Transport/InwardRectifier.lean#L111)
- [CellsProofs.Transport.InwardRectifier.slope_bound](../CellsProofs/Transport/InwardRectifier.lean#L140)

Direct proof subject `cells.inward_rectifier_linear_driving_force@1`

Proof sources [Mathlib’s lower bound on the hyperbolic sine](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Trigonometric/Deriv.lean#L636)

## Numerical comparison

**Checked.** All three equivalent normalizations gave 0.5520533 pA and identical transfer and heat, including the smallest normal float64 potassium reference. All 360 voltage controls passed. A positive subnormal reference (5 × 10⁻³²⁴ mM) was refused during definition checking. The original overflow remains at the earlier engine revision.

**Engine** `resolved_pump_tissue@3`, `cells.inward_rectifier_linear_driving_force@1`

[Admitted reference concentration](https://github.com/Eidosoma/Cells/blob/8f9bc0500f362096155640cd843a69f2dabc6107/src/cells/kinds/passive_routes.py#L242) · [Subnormal reference refusal](https://github.com/Eidosoma/Cells/blob/8f9bc0500f362096155640cd843a69f2dabc6107/tests/unit/test_inward_rectifier_route.py#L135) · [Current and conductance factor](https://github.com/Eidosoma/Cells/blob/8f9bc0500f362096155640cd843a69f2dabc6107/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L81) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/checks/inward_rectifier.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/PROGRESS.md#claim-source-review)

[Tested engine 8f9bc0500f36](https://github.com/Eidosoma/Cells/commit/8f9bc0500f362096155640cd843a69f2dabc6107) · [Evidence checkpoint 8f269af4c8b7](https://github.com/Eidosoma/Cells/commit/8f269af4c8b79150020b47a86dd71da848d91714)

**Engine** `resolved_pump_tissue@3`, `cells.inward_rectifier_linear_driving_force@1`

[Overflow-safe concentration factor](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L69) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/inward_rectifier.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `resolved_pump_tissue@3`, `cells.inward_rectifier_linear_driving_force@1`

[Law and Nernst potential](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L49) · [Conductance scaling](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L71) · [Voltage-free slope bound](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L107) · [Passive tissue rates](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/kinds/passive_routes.py#L512) · [Tissue admission](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/models/surface_pump_v3.py#L1558) · [Independent derivatives](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/validation/core_seams/references/exact.py#L88) · [Closed tissue pair](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/tests/unit/test_inward_rectifier_route.py#L53) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/checks/inward_rectifier.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

[Tested engine ced58d2a1edc](https://github.com/Eidosoma/Cells/commit/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984) · [Evidence checkpoint 40dfe4de2a04](https://github.com/Eidosoma/Cells/commit/40dfe4de2a04559196bddef7e32c01cffc056e7b)

## Biological evidence

**Mixed.** Kir4.1 unitary current 60 mV below reversal, inward unitary slope conductance and the shift in reversal as external potassium changes.

- [Inward Kir4.1 unitary slope conductance follows the square root of external potassium across preparations.](../WET_LAB_EVIDENCE.md#pair-kir41-slope-scaling) · Different experimental results
- [Raising external potassium shifts the reversal of Kir4.1 or a Kir-dominated Müller-cell current to more positive voltages.](../WET_LAB_EVIDENCE.md#pair-kir-potassium-reversal) · Supported by both studies

Reversal moved toward positive voltages when external potassium rose in two preparations. The inward unitary conductance increased with potassium in both recombinant series, with different concentration dependence.

**Unit** pA

### tada1998_kir41@1

Cloned rat Kir4.1 in HEK293T cell-attached patches at about 25 °C, three patches per concentration. Panel C gives reversal, B(b) gives unitary currents and D fits the inward slope conductances from the same patch series. [Tada et al. (1998), Fig. 4B–D](https://doi.org/10.2170/jjphysiol.48.71)

- **Evidence role** held out from fitting
- **Fit** 153 mM current amplitude
- **Evaluation** 15, 21, 35 and 63 mM at a common −60 mV drive
- **Excluded** Rabbit Müller cell series
- **Observed** -0.59 pA
- **Predicted** -0.385 pA

Currents are approximate graph readings interpolated after reading the reversal for each series. Some reversal markers overlap. Per-point numerical uncertainties are unavailable.

At 15 mM external K the current magnitude fell less than the model predicted, as it did at the other three held-out concentrations. The model’s −59.67 mV shift in reversal agreed with the approximately −60 mV measured. [Dataset manifest](../checks/data/tada1998_kir41.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

### edvinsson2011_kir41_conductance@1

Human Kir4.1 in cell-attached Xenopus oocyte patches, pH 7.4, pipette magnesium 1 mM. Changes in pipette KCl were balanced by NaCl. Figure 7B–C and adjacent Results [Edvinsson, Shah and Palmer (2011), Fig. 7B–C](https://doi.org/10.4161/chan.5.3.15827)

- **Evidence role** descriptive

10 and 40 mM are approximate figure readings. The 110 mM value is in the text. Figure errors were plotted without numerical errors or a stated sample count for each point.

At 10, 40 and 110 mM external K the inward slope was approximately 8, 19 and 23 pS. The authors fitted saturation (maximum 24.4 pS, half-maximal K 16.7 mM, exponent 1.4). Their modeled reversal offsets supply no independent reversal measurement. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### kucheryavykh2008_muller_reversal@1

Whole-cell recording from retinal glia with 100 mM intracellular K and 3 mM added intracellular spermine. Figure 5B, two raw current–voltage curves in a frog Müller cell [Kucheryavykh et al. (2008), Fig. 5B](https://doi.org/10.1002/glia.20652)

- **Evidence role** descriptive

Approximate visual shifts within one cell. No numerical uncertainty on the crossings. Native current may include other channels.

A tenfold increase in external K moved the raw current crossing about +50 mV. The separate breakpoint for fast block moved about +100 mV. Native Müller-cell current supports the direction of reversal with a less specific channel assignment. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
