<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Finite binding forms have normalized Boltzmann weights

At fixed free ligand activities, the fraction in each form equals its effective Boltzmann weight divided by the finite partition sum. Isomers with the same ligand counts can be combined into one registered form by summing their weights. This preserves their aggregate occupancy at every such set of activities.

## Assumptions

- A binder has finitely many present forms and a positive total. Equilibrium is conditional on finite positive free ligand activities and a fixed positive inverse temperature. The tissue solver supplies those activities when only totals are given.
- Counts relative to the base form may be signed. All standard potentials use the same temperature and standard concentration. The engine uses ideal concentration activities x/c₀. A concentration-dependent activity coefficient would require its own model.
- Microscopic states within a registered form have the same ligand counts. Each state is counted once, and the group’s standard potential is −log Σ exp(−μᵢ°/RT) in units of RT.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.BindingEnsemble.logWeight_change_frame](../CellsProofs/Chemistry/BindingEnsemble.lean#L24)
- [CellsProofs.Chemistry.BindingEnsemble.fraction_shift](../CellsProofs/Chemistry/BindingEnsemble.lean#L37)
- [CellsProofs.Chemistry.BindingEnsemble.fraction_from_log_sum](../CellsProofs/Chemistry/BindingEnsemble.lean#L43)
- [CellsProofs.Chemistry.BindingEnsemble.fraction_grouped](../CellsProofs/Chemistry/BindingEnsemble.lean#L50)
- [CellsProofs.Chemistry.BindingEnsemble.group_log_weight](../CellsProofs/Chemistry/BindingEnsemble.lean#L57)
- [CellsProofs.Chemistry.BindingEnsemble.binding_fraction_from_isomers](../CellsProofs/Chemistry/BindingEnsemble.lean#L68)
- [CellsProofs.Chemistry.BindingEnsemble.equal_state_log_weight](../CellsProofs/Chemistry/BindingEnsemble.lean#L80)

Direct proof subject `cells.binding.rapid_binding@1`

Proof sources [Physlib finite partition, specialized on the optional v4.22.0 pin](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/CanonicalEnsemble/Finite.lean#L119-L125) · [Physlib single-state probability](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/CanonicalEnsemble/Basic.lean#L388-L394) · [Physlib Boltzmann-constant axiom](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/BoltzmannConstant.lean#L20-L30) · [Cells specialization compiled with Physlib](../checks/physlib/BindingEnsemble.lean)

## Numerical comparison

**Checked.** On both NumPy and JIT-compiled JAX CPU, 536 form fractions across 80 S1–S7 states agreed with an 80-digit standard-potential partition to within 7.78 × 10⁻¹⁶ in absolute fraction. All 52 padded entries were zero. The six-form H/Mg tissue read stayed within the registered tolerance. The isomer control distinguished 1/2, 2/3 and 4/5 occupied.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Form normalization and concentrations](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/reactions/rapid_binding.py#L100) · [Registry potentials and standard concentration](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/registry/species_registry.py#L1435) · [Tissue stage read](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/kinds/proton_buffer.py#L377) · [Manufactured conditions and standard potentials](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/core_seams/references/reference_inputs.json) · [Independent reference concentrations and tolerances](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/core_seams/references/designs/core_seams_reference_values.json) · [Binding kernel fixtures](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_rapid_binding_kernel.py#L60) · [Tissue fixture and read](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_rapid_binding_world.py#L232) · [Initialization used by the tissue check](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_proton_buffer_kind.py) · [Measured Mg–ATP inputs](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/checks/data/mgatp_binding.json) · [Exact binding theorem](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/CellsProofs/Chemistry/BindingEnsemble.lean) · [Optional Physlib specialization](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/checks/physlib/BindingEnsemble.lean) · [Pinned Physlib reproduction](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/checks/physlib/binding.sh) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/checks/binding_ensemble.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/44e6c613f0da21fd5837dee756aa7cbdda882368/lean/PROGRESS.md#binding-form-ensemble)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint 44e6c613f0da](https://github.com/Eidosoma/Cells/commit/44e6c613f0da21fd5837dee756aa7cbdda882368)

## Biological evidence

**Open.** ATP fraction carrying Mg at measured free Mg, pH, temperature and solution composition. The individual H/Mg microscopic forms would require additional resolved measurements.

- [A single apparent Mg–ATP dissociation constant transfers between these near-matched pH and temperature conditions.](../WET_LAB_EVIDENCE.md#pair-mgatp-apparent-affinity) · Different experimental results

At pH 7.2 and 37 °C, transferring an independently measured apparent affinity between two preparations underpredicted Mg-bound ATP by about 0.17. Their solution compositions and measurement methods differ.

**Unit** fraction of ATP carrying Mg

### ward1998_mgatp_zhang1997_affinity

Three mM ATP in MOPS/KCl at pH 7.2, 37 °C and ionic strength 0.15 M. Matched aliquots supplied the fluorescent free-Mg and phosphorus NMR measurements. The two-form prediction uses Zhang et al.’s macroelectrode Kd at the same pH and temperature in a muscle-like solution of ionic strength 0.156 M. [Zhang et al. (1997)](https://doi.org/10.1006/abio.1997.2238) Rightmost marker in Figure 1, about 230 µM free Mg and a bound/unbound ATP ratio of 8.7. Dividing the ratio by one plus the ratio gives the observed fraction. [Ward et al. (1998), Fig. 1](https://cds.ismrm.org/ismrm-1998/PDF6/p1693.pdf)

- **Evidence role** held out from fitting
- **Fit** Zhang et al. apparent Kd at pH 7.2, 87.4 µM
- **Evaluation** Ward et al. Figure 1 rightmost aggregate Mg-bound fraction
- **Excluded** Ward et al. same-figure fitted Kd, 27.7 µM, Zhang et al. pH 6.7 and 7.7 Kd values
- **Observed** 0.897 fraction of ATP carrying Mg
- **Predicted** 0.725 fraction of ATP carrying Mg

Zhang et al. report SD 4.9 µM over four measurements. Graph-reading precision is about ±5 µM in free Mg and ±0.1 in bound/unbound ratio. Ward et al. give no sampling uncertainty for this individual marker.

A single transferred apparent Kd misses the aggregate fraction in this preparation. Quantitative validation of individual H/Mg occupancies requires matched solution conditions and form-resolved evidence. [Dataset manifest](../checks/data/mgatp_binding.json) · [Comparison verdict](../PROGRESS.md#binding-form-ensemble)

### zhang1997_mgatp_affinity@1

Mg-sensitive macroelectrode with EDTA calibration, 37 °C and ionic strength 0.156 M. Primary report, pH 7.2 in the normal muscle-like background. Numerical series in the linked manifest. [Zhang et al. (1997), normal muscle-like solution at pH 7.2](https://doi.org/10.1006/abio.1997.2238)

- **Evidence role** calibration
- **Fit** Apparent Mg–ATP affinity used for the Ward prediction

SD 4.9 µM across four measurements.

The apparent dissociation constant was 87.4 µM. This supplied the external affinity used to predict Ward’s aggregate Mg-bound ATP fraction. [Dataset manifest](../checks/data/mgatp_binding.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
