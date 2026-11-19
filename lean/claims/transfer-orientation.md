<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Edge orientation preserves each compartment’s transfer balance

Reversing any subset of edge orientations and their signed fluxes preserves each compartment’s credit or debit.

## Assumptions

- Every transfer is booked once at its sender and once at its receiver. The edge set is finite and multiple edges may share a compartment.

## Lean proof

**Proved**

- [CellsProofs.Accounting.nodeChange_reorient](../CellsProofs/Accounting/Transfer.lean#L26)

## Numerical comparison

**Checked.** The per-cell comparison passed for the declared owners. Swapping owners alone preserved the global total and produced a per-cell discrepancy of 2.40 × 10⁻⁴ fmol/s.

**Engine** `resolved_pump_tissue@3`, `constant_field@1`

[Junction flux](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/junctions/selective.py#L19) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/electrochemistry.py#L17) · [Flux booking](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/numerics/surface_transport.py#L318) · [Surface comparisons](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_transport.py#L103) · [Per-cell tissue ledger](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_pump_v3_imex.py#L80) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/checks/constant_field.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison)

[Tested engine 109a7355ed85](https://github.com/Eidosoma/Cells/commit/109a7355ed85ff2e1e5a9c884c32801c07a2fd72) · [Evidence checkpoint 627c376c463a](https://github.com/Eidosoma/Cells/commit/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd)

## Biological evidence

**Open.** Net ion gain or loss in each of two identified compartments over the same transfer interval.

Paired clamp recordings showed equal and opposite junctional currents. Calibrated gain and loss of the same ion in both cells remain unmeasured. [Wang and Veenstra, Fig. 1A and C](https://pubmed.ncbi.nlm.nih.gov/9101407/)

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
