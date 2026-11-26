<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A blocked junction carries zero flux

Setting the effective transport scale to zero gives zero junction flux at every voltage and concentration difference.

## Assumptions

- The constant-field route multiplies the concentration-dependent term by its effective area, permeability and opening scale.

## Lean proof

**Proved**

- [CellsProofs.Transport.flux_blocked](../CellsProofs/Transport/ConstantField.lean#L58)

Direct proof subject `cells.route.constant_field@1`

## Numerical comparison

**Checked.** The surface blocking and equilibrium tests passed on CPU.

**Engine** `resolved_pump_tissue@3`, `constant_field@1`

[Junction flux](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/junctions/selective.py#L19) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/electrochemistry.py#L17) · [Flux booking](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/numerics/surface_transport.py#L318) · [Surface comparisons](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_transport.py#L103) · [Per-cell tissue ledger](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_pump_v3_imex.py#L80) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/checks/constant_field.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison)

[Tested engine 109a7355ed85](https://github.com/Eidosoma/Cells/commit/109a7355ed85ff2e1e5a9c884c32801c07a2fd72) · [Evidence checkpoint 627c376c463a](https://github.com/Eidosoma/Cells/commit/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd)

## Biological evidence

**Open.** Ion transfer rate attributable to a junction under a specified blocking condition, with the assay detection limit.

Heptanol suppressed junctional current in a bovine epithelial cell pair, and the current returned after washout. The trace has no reported detection threshold for residual ion flux. [Wang et al., Fig. 2E–F](https://pubmed.ncbi.nlm.nih.gov/20089928/)

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
