<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Rounding and rejection of the initial charge balance

A balanced ionic inventory passes a closed charge tolerance T whenever T covers the accumulated rounding allowance E. A true charge error larger than T + E in magnitude is detected. At a midpoint in the 2²⁰-fmol range, rounding the fixed background alone can exceed the original 10⁻²⁰ C tolerance.

## Assumptions

- The builder and reader use the same finite stored valence-weighted ion amounts and positive charge conversion in C/fmol. The builder forms the background by subtracting their rounded sum from the declared charge divided by the conversion.
- Each arithmetic result satisfies its stated absolute error allowance. Four allowances are in fmol and the final two in coulombs. Half a local spacing bounds a nearest-grid result with either tie choice. The native replay checks each rounding premise against exact rational arithmetic for the sampled inputs.
- A planted background change is its actual stored difference in fmol. The distinction between a genuine mismatch and rounding is guaranteed when their bounds are separated.

## Lean proof

**Proved**

- [CellsProofs.Tissue.ChargeAnchor.nearest_grid_error](../CellsProofs/Tissue/ChargeAnchor.lean#L11)
- [CellsProofs.Tissue.ChargeAnchor.residual_error](../CellsProofs/Tissue/ChargeAnchor.lean#L24)
- [CellsProofs.Tissue.ChargeAnchor.balanced_admitted](../CellsProofs/Tissue/ChargeAnchor.lean#L42)
- [CellsProofs.Tissue.ChargeAnchor.defect_refused](../CellsProofs/Tissue/ChargeAnchor.lean#L47)
- [CellsProofs.Tissue.ChargeAnchor.midpoint_residual](../CellsProofs/Tissue/ChargeAnchor.lean#L55)
- [CellsProofs.Tissue.ChargeAnchor.midpoint_exceeds_floor](../CellsProofs/Tissue/ChargeAnchor.lean#L66)

Proof sources [Mathlib nearest-integer distance, imported and rescaled to the local spacing](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Round.lean#L190) · [Charge-anchor diagnosis and scope of the engine correction D333](https://github.com/Eidosoma/Cells/blob/23bf52341b6a096dc19d69d7dac509d4f46eeb00/docs/DECISIONS.md#L10542)

## Numerical comparison

**Checked.** On 82c26ddd the native parser admitted all 15 balanced inputs and rejected both deliberately mischarged controls. The seven balanced refusals on cd3b7b09 and 8760d5b3 remain in the original record. Exact rational arithmetic verified all six local rounding allowances. Both signed midpoint controls had absolute residual 1.123237099 × 10⁻²⁰ C.

**Engine** `resolved_pump_tissue@3`

[XC0 node builder](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/validation/xenopus_bioelectric/xc0_worlds.py#L164) · [Public XC0 fixture inputs](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/validation/xenopus_bioelectric/references/reference_inputs.json) · [Model parsing entry point](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/definitions/specs.py#L993) · [Definition check during model parsing](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/definitions/surface_tissue_spec.py#L362) · [Charge per fmol](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/laws/electrochemistry.py#L14) · [Fixed-background and anchor comparison](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/models/surface_tissue.py#L440) · [Charge error and threshold separation theorems](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/CellsProofs/Tissue/ChargeAnchor.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/checks/charge_anchor.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/PROGRESS.md#xc0-charge-anchor)

[Tested engine 8760d5b338a1](https://github.com/Eidosoma/Cells/commit/8760d5b338a1f7e9a930a8492c434efaa50815e7) · [Evidence checkpoint 39ddff471654](https://github.com/Eidosoma/Cells/commit/39ddff47165473b96d594a23e5a7696f60f81c66)

**Engine** `resolved_pump_tissue@3`

[XC0 node builder](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/validation/xenopus_bioelectric/xc0_worlds.py#L164) · [Public XC0 fixture inputs](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/validation/xenopus_bioelectric/references/reference_inputs.json) · [Model parsing entry point](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/src/cells/definitions/specs.py#L993) · [Definition check during model parsing](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/src/cells/definitions/surface_tissue_spec.py#L362) · [Charge per fmol](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/src/cells/laws/electrochemistry.py#L14) · [Fixed-background and anchor comparison](https://github.com/Eidosoma/Cells/blob/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b/src/cells/models/surface_tissue.py#L443) · [Charge error and threshold separation theorems](https://github.com/Eidosoma/Cells/blob/5c33f2e71fe9d31d29c403c0cdcf7f46e10b489e/lean/CellsProofs/Tissue/ChargeAnchor.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/5c33f2e71fe9d31d29c403c0cdcf7f46e10b489e/lean/checks/charge_anchor.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/5c33f2e71fe9d31d29c403c0cdcf7f46e10b489e/lean/PROGRESS.md#xc0-scale-aware-main)

[Tested engine 82c26ddd3a76](https://github.com/Eidosoma/Cells/commit/82c26ddd3a7616130f8a5cbddcf2ba2b1492633b) · [Evidence checkpoint 5c33f2e71fe9](https://github.com/Eidosoma/Cells/commit/5c33f2e71fe9d31d29c403c0cdcf7f46e10b489e)

## Biological evidence

**Open.** This arithmetic tolerance compares two calculations on the same declared inputs. An experimental test of the charge balance itself would need mobile and fixed charge, capacitance and potential from the same cell.

- [The sum of independently measured mobile and fixed charge in a native oocyte equals its capacitive charge.](../WET_LAB_EVIDENCE.md#pair-xc0-native-oocyte-charge) · Comparison unresolved

**Unit** C

### guizouarn2004_native_oocyte_ions@1

Native Xenopus oocytes. Na and K measured by flame photometry, Cl by equilibrium tracer uptake, and membrane potential by electrodes. Experimental Procedures (ion and water measurements, electrophysiology) and Table I, noninjected controls. [Guizouarn et al. (2004), Table I, controls](https://doi.org/10.1074/jbc.M311920200)

- **Evidence role** descriptive

Group means ± SE. The water estimate used pooled wet/dry weights and a trapped-water correction. Individual water uncertainty and overlap between the ion and voltage samples are unspecified.

The same group previously reported the −56.8 mV control (Table 1, 2001). These observations supply partial mobile-ion and voltage measurements. Treating a difference of their means as measured fixed charge would make the closure test circular. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### costa1989_native_oocyte_ions@1

Native Xenopus laevis oocytes, stages IV–V. Ion-selective electrodes estimated intracellular free ions on a concentration scale. Summary, item 7, intracellular ion-selective microelectrode measurements. [Costa et al. (1989), summary item 7](https://doi.org/10.1113/jphysiol.1989.sp017649)

- **Evidence role** descriptive

Separate sample counts per ion. The quoted equilibrium potentials for each species were calculated from concentrations. Those values cannot substitute for a measured membrane voltage in a charge balance.

The free-ion values give an independent scale for the three species. Converting activities to a total inventory additionally needs activity coefficients, binding and cell water. Fixed charge remains unmeasured. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
