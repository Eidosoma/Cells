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

**Failed.** A 360-state compiled panel passed against 60-digit currents and derivatives. Two equivalent reference settings produced identical one-step transfer and heat. A third, also finite, had the same 0.5520533 pA reference current but overflowed in c_out/K_ref and was refused during definition validation.

**Engine** `resolved_pump_tissue@3`, `cells.inward_rectifier_linear_driving_force@1`

[Law and Nernst potential](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L49) · [Conductance scaling](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L71) · [Voltage-free slope bound](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L107) · [Passive tissue rates](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/kinds/passive_routes.py#L512) · [Tissue admission](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/models/surface_pump_v3.py#L1558) · [Independent derivatives](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/validation/core_seams/references/exact.py#L88) · [Closed tissue pair](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/tests/unit/test_inward_rectifier_route.py#L53) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/checks/inward_rectifier.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

[Tested engine ced58d2a1edc](https://github.com/Eidosoma/Cells/commit/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984) · [Evidence checkpoint 40dfe4de2a04](https://github.com/Eidosoma/Cells/commit/40dfe4de2a04559196bddef7e32c01cffc056e7b)

## Biological evidence

**Mixed.** Kir4.1 unitary current 60 mV below each measured reversal potential as external potassium changes.

**Unit** pA

### tada1998_kir41@1

Cloned rat Kir4.1 in HEK293T cell-attached patches at about 25 °C, three patches per concentration. Panel C gives reversal, B(b) gives the unitary currents and D gives an independently reported fit to inward slope conductances. [Tada et al. (1998), Fig. 4B–D](https://doi.org/10.2170/jjphysiol.48.71)

- **Evidence role** held out from fitting
- **Fit** 153 mM current amplitude
- **Evaluation** 15, 21, 35 and 63 mM at a common −60 mV drive
- **Excluded** Rabbit Müller cell series
- **Observed** -0.59 pA
- **Predicted** -0.385 pA

Currents are approximate graph readings interpolated after reading the reversal for each series. Some reversal markers overlap. Per-point numerical uncertainties are unavailable.

At 15 mM external K the current magnitude fell less than the model predicted, as it did at the other three held-out concentrations. The model’s −59.67 mV shift in reversal agreed with the approximately −60 mV measured. [Dataset manifest](../checks/data/tada1998_kir41.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
