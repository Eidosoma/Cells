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

**Failed.** The native parser refused seven of 15 balanced inputs and correctly rejected both deliberately mischarged inputs on cd3b7b09 and 8760d5b3. The full results were byte-identical after FR-17 landed. The scale-aware criterion classified all 17. Exact rational arithmetic confirmed all six local allowances on each case. In the two signed midpoint controls at 1.5 × 2²⁰ fmol the unperturbed absolute residual was 1.123237099 × 10⁻²⁰ C. This check runs at definition time.

**Engine** `resolved_pump_tissue@3`

[XC0 node builder](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/validation/xenopus_bioelectric/xc0_worlds.py#L164) · [Public XC0 fixture inputs](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/validation/xenopus_bioelectric/references/reference_inputs.json) · [Model parsing entry point](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/definitions/specs.py#L993) · [Definition check during model parsing](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/definitions/surface_tissue_spec.py#L362) · [Charge per fmol](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/laws/electrochemistry.py#L14) · [Fixed-background and anchor comparison](https://github.com/Eidosoma/Cells/blob/8760d5b338a1f7e9a930a8492c434efaa50815e7/src/cells/models/surface_tissue.py#L440) · [Charge error and threshold separation theorems](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/CellsProofs/Tissue/ChargeAnchor.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/checks/charge_anchor.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/39ddff47165473b96d594a23e5a7696f60f81c66/lean/PROGRESS.md#xc0-charge-anchor)

[Tested engine 8760d5b338a1](https://github.com/Eidosoma/Cells/commit/8760d5b338a1f7e9a930a8492c434efaa50815e7) · [Evidence checkpoint 39ddff471654](https://github.com/Eidosoma/Cells/commit/39ddff47165473b96d594a23e5a7696f60f81c66)

## Biological evidence

**Open.** This arithmetic tolerance compares two calculations on the same declared inputs. An experimental test of the charge balance itself would need mobile and fixed charge, capacitance and potential from the same cell.

**Unit** C

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
