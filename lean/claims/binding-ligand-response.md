<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Total ligand increases with its own free concentration

At fixed binder totals and other free ligand concentrations, increasing one free ligand strictly increases its total. The matrix of derivatives of totals with respect to free log concentrations is symmetric positive definite. Filling unheld coordinates with the engine’s identity block preserves this property. With the same binder totals and other free ligands fixed, the increase in total ligand is at least the increase between any two positive free concentrations.

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
- [CellsProofs.Chemistry.BindingResponse.free_increment_le_total_increment](../CellsProofs/Chemistry/BindingResponse.lean#L178)

Direct proof subject `cells.rapid_binding@1`

Proof sources [Mathlib positive definite diagonal, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L362-L370) · [Mathlib weighted positive semidefinite matrix product, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L69-L76) · [Mathlib sum of a positive definite and a positive semidefinite matrix, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L420-L426) · [Mathlib strict monotonicity from a positive derivative, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L382-L385) · [Mathlib monotonicity from a nonnegative derivative, imported for the finite concentration increment](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L413-L416)

Uses [Finite binding forms have normalized Boltzmann weights](binding-form-ensemble.md)

## Numerical comparison

**Checked.** NumPy, compiled JAX CPU and the differentiated conservation residual each matched all 303 entries of an 80-digit centered covariance across 80 S1–S7 states. The largest absolute error was 2.45 × 10⁻¹⁴ mM. All nine proton-release states had a negative H–Mg entry and a positive Mg diagonal. Checks included empty binders, unheld coordinates and a missing-covariance control. For free ligand of 0.25–4 mM and a single site with Kd = 1 mM, four finite total/free increment ratios matched the analytical values on compiled CPU. The empty buffer gave equality at each step. With 2 mM binder the ratios ranged from 2.067 to 1.133.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Form moments, conservation residual and Hessian](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/laws/reactions/rapid_binding.py#L100-L142) · [Inverse sensitivity of the closure](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/laws/reactions/rapid_binding.py#L450) · [Registered standard potentials and manufactured totals](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/core_seams/references/reference_inputs.json) · [Reference free concentrations](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/core_seams/references/designs/core_seams_reference_values.json) · [S1–S7 inverse sensitivity and central differences](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_rapid_binding_kernel.py#L476) · [H/Mg tissue run](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_rapid_binding_world_two_ligands.py#L31) · [Exact response proof](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/CellsProofs/Chemistry/BindingResponse.lean) · [Normalized form weights](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/CellsProofs/Chemistry/BindingEnsemble.lean) · [ATP titration markers](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/data/ward1998_mgatp_titration.json) · [Independent Mg–ATP affinity](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/data/mgatp_binding.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/checks/binding_response.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e9510ee6724149a27cfdb035bc03be59fae8bf36/lean/PROGRESS.md#binding-ligand-response)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint e9510ee67241](https://github.com/Eidosoma/Cells/commit/e9510ee6724149a27cfdb035bc03be59fae8bf36)

**Engine** `cells.rapid_binding@1`

[Conservation residual from the equilibrium form weights](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/laws/reactions/rapid_binding.py#L124) · [Construction of the single-site test network](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/laws/reactions/rapid_binding.py#L546) · [Finite total-ligand bound](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/CellsProofs/Chemistry/BindingResponse.lean) · [Observed ionized and total calcium in two albumin experiments](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/checks/data/paired_calibration_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/checks/binding_buffer_capacity.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/PROGRESS.md#paired-calibration-and-leaflet-packing)

[Tested engine 1e40fc16ade2](https://github.com/Eidosoma/Cells/commit/1e40fc16ade2244aa45a3f18f3055dd60819a2e7) · [Evidence checkpoint 22587f8d5e38](https://github.com/Eidosoma/Cells/commit/22587f8d5e38ae18d775b7a65c91fb10e9277991)

## Biological evidence

**Open.** ATP Mg occupancy and proton release during Mg titration, and the paired change in measured total and ionized calcium at fixed bovine albumin concentration.

- [At fixed albumin concentration near neutral pH, increasing measured free calcium by a finite amount requires at least as large an increase in total calcium.](../WET_LAB_EVIDENCE.md#pair-albumin-calcium-buffering) · Supported by both studies

Independent albumin experiments show total calcium rising by at least the free-calcium increment. The total-Mg slope and fixed-pH proton response in the separate ATP system remain open.

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

### spicer1952_atp_acidification

The controlled variable was added magnesium salt. Bulk pH could change during the titration. The ATP curve and accompanying text record a pH decrease as magnesium salt was added to a 2.5 mM ATP solution. [Spicer (1952), Fig. 2, p. 304](https://doi.org/10.1016/S0021-9258(18)44837-5)

- **Evidence role** descriptive

Figure 2 gives no free-Mg measurement or proton-equivalent count. A temperature specific to the titration could not be verified.

The acidification supports the direction of proton release in this ATP preparation. A fixed-pH measurement is still needed to quantify the cross-response. [Dataset manifest](../checks/data/binding_equilibrium_measurements.json) · [Comparison verdict](../PROGRESS.md#binding-proton-release-observation)

### besarab1981_bsa_calcium@1

Bovine albumin 4.97 g/dL in retentate at 37 °C. Paired ion-selective electrode and atomic-absorption determinations. Table 1, retentate after filtration, ionized and total calcium columns [Besarab, DeGuzman and Swanson (1981), Table 1](https://doi.org/10.1136/jcp.34.12.1361)

- **Evidence role** descriptive

Duplicate ionized readings, other entries based on at least four measurements. Reported assay CVs 2.6% for ionized and 2.1% for total calcium. Pointwise errors and free Mg are unavailable.

At five dose levels total Ca increased from 1.03 to 3.23 mM and ionized Ca from 0.45 to 1.56 mM. Each of the four successive increases in total exceeded the corresponding free increment. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### gunther1998_bsa_calcium@1

40 g/L bovine albumin with 2.7 mM palmitate at 37 °C. Ion-selective electrode and atomic absorption. Table 1, rows C and D, second page of the paper, Magnesium-Bulletin 20 (1998) [Günther and Ising (1998), Table 1, rows C and D](https://www.magnesium-ges.de/download/binding-of-mg2-and-ca2-to-serum-albumin-no-effect-of-free-fatty-acids/?wpdmdl=505#page=2)

- **Evidence role** descriptive

Nine measurements per condition pooled across a magnesium-addition series (0.2–4.15 mM). Values for free calcium are means ± SEM. No sampling error for total calcium is given.

At pH 7.324 and 7.323, free Ca rose from 0.416 ± 0.008 to 1.934 ± 0.023 mM and total Ca from 0.523 to 2.605 mM. The endpoint ratio was 1.37. Pooling across Mg additions limits a fixed-free-Mg interpretation. [Dataset manifest](../checks/data/paired_calibration_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
