<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Total ligand increases with its own free concentration

At fixed binder totals and other free ligand concentrations, increasing one free ligand strictly increases its total. The matrix of derivatives of totals with respect to free log concentrations is symmetric positive definite. Filling unheld coordinates with the engine’s identity block preserves this property.

## Assumptions

- Each binder has finitely many present equilibrium forms with normalized weights. Temperature and standard potentials are fixed. Ligand counts relative to the base form may be signed.
- Free concentrations are positive and binder totals are nonnegative. The derivative varies one free log concentration while holding the other free concentrations fixed. The formula uses exact real arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.BindingResponse.logWeight_perturb](../CellsProofs/Chemistry/BindingResponse.lean#L100)
- [CellsProofs.Chemistry.BindingResponse.covariance_eq_centered](../CellsProofs/Chemistry/BindingResponse.lean#L34)
- [CellsProofs.Chemistry.BindingResponse.hasDerivAt_mean](../CellsProofs/Chemistry/BindingResponse.lean#L47)
- [CellsProofs.Chemistry.BindingResponse.response_entry_hasDerivAt](../CellsProofs/Chemistry/BindingResponse.lean#L132)
- [CellsProofs.Chemistry.BindingResponse.totalAlong_strictMono](../CellsProofs/Chemistry/BindingResponse.lean#L74)
- [CellsProofs.Chemistry.BindingResponse.total_strictMonoOn_free](../CellsProofs/Chemistry/BindingResponse.lean#L92)
- [CellsProofs.Chemistry.BindingResponse.response_posDef](../CellsProofs/Chemistry/BindingResponse.lean#L147)
- [CellsProofs.Chemistry.BindingResponse.masked_response_posDef](../CellsProofs/Chemistry/BindingResponse.lean#L161)

Direct proof subject `cells.rapid_binding@1`

Proof sources [Mathlib positive definite diagonal, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L362-L370) · [Mathlib weighted positive semidefinite matrix product, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L69-L76) · [Mathlib sum of a positive definite and a positive semidefinite matrix, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L420-L426) · [Mathlib strict monotonicity from a positive derivative, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L382-L385)

Uses [Finite binding forms have normalized Boltzmann weights](binding-form-ensemble.md)

## Numerical comparison

**Checked.** NumPy, compiled JAX CPU and the differentiated conservation residual each matched all 303 entries of an 80-digit centered covariance across 80 S1–S7 states. The largest absolute error was 2.45 × 10⁻¹⁴ mM. All nine proton-release states had a negative H–Mg entry and a positive Mg diagonal. Checks included empty binders, unheld coordinates and a missing-covariance control.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Form moments, conservation residual and Hessian](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/laws/reactions/rapid_binding.py#L100-L142) · [Inverse sensitivity of the closure](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/laws/reactions/rapid_binding.py#L450) · [Registered standard potentials and manufactured totals](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/core_seams/references/reference_inputs.json) · [Reference free concentrations](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/core_seams/references/designs/core_seams_reference_values.json) · [S1–S7 inverse sensitivity and central differences](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_rapid_binding_kernel.py#L476) · [H/Mg tissue run](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_rapid_binding_world_two_ligands.py#L31) · [Exact response proof](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/CellsProofs/Chemistry/BindingResponse.lean) · [Normalized form weights](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/CellsProofs/Chemistry/BindingEnsemble.lean) · [ATP titration markers](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/data/ward1998_mgatp_titration.json) · [Independent Mg–ATP affinity](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/data/mgatp_binding.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/binding_response.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/PROGRESS.md#binding-ligand-response)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint e9510ee67241](https://github.com/Eidosoma/Cells/commit/e9510ee6724149a27cfdb035bc03be59fae8bf36)

## Biological evidence

**Open.** ATP Mg occupancy at fixed ATP, pH and temperature across measured free Mg. Quantitative self and cross-responses would require measured changes in total Mg and proton inventory.

Two titration points support increasing ATP Mg occupancy. The total-Mg slope and the proton response to Mg remain unmeasured in these data.

**Unit** change in fraction of ATP carrying Mg

### ward1998_mgatp_direction

Fixed 3 mM ATP at pH 7.2, 37 °C and ionic strength 0.15 M. Matched aliquots at each level supplied free Mg by fluorescence and aggregate occupancy by phosphorus NMR. The engine’s two-form comparison uses an independent apparent affinity from a muscle-like solution. [Zhang et al.](https://doi.org/10.1006/abio.1997.2238) Distinct squares at approximately 130 and 230 µM free Mg have bound/unbound ATP ratios of 4.2 and 8.7. These give Mg occupancies of 0.808 and 0.897. [Ward et al. (1998), Fig. 1](https://cds.ismrm.org/ismrm-1998/PDF6/p1693.pdf)

- **Evidence role** held out from fitting
- **Fit** Zhang et al. apparent Mg–ATP Kd of 87.4 µM at 37 °C and pH 7.2
- **Evaluation** Change in ATP Mg occupancy between the two Figure 1 samples
- **Excluded** Ward’s fitted line and all other markers
- **Observed** 0.089 change in fraction of ATP carrying Mg
- **Predicted** 0.127 change in fraction of ATP carrying Mg

Reading precision is about ±5 µM and ±0.1 in bound/unbound ratio. The figure pools seven runs and gives no pointwise sampling errors, run identities or measured total Mg.

The model gives the observed direction and overpredicts the increase by 3.7 percentage points. Solution compositions differ. The H–Mg cross-response remains open. [Dataset manifest](../checks/data/ward1998_mgatp_titration.json) · [Comparison verdict](../PROGRESS.md#binding-ligand-response)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
