<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Reversing a junction reverses its flux

Exchanging the concentrations at the two ends of a constant-field junction and reversing the voltage difference negates the signed flux.

## Assumptions

- The ion, temperature, area, permeability and opening are the same in both orientations. Voltage is sender potential minus receiver potential, scaled by zF/(RT).
- The proof treats both the analytic Bernoulli factor and the engine’s near-zero series in real arithmetic. A floating-point error bound for the series remains open.

## Lean proof

**Proved**

- [CellsProofs.Transport.flux_reverse](../CellsProofs/Transport/ConstantField.lean#L40)

Direct proof subject `cells.constant_field@1`

## Numerical comparison

**Checked.** The CPU surface tests exercised reversed routes, multiple patches and padding against the independent flux reference.

**Engine** `resolved_pump_tissue@3`, `constant_field@1`

[Junction flux](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/junctions/selective.py#L19) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/electrochemistry.py#L17) · [Flux booking](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/numerics/surface_transport.py#L318) · [Surface comparisons](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_transport.py#L103) · [Per-cell tissue ledger](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_pump_v3_imex.py#L80) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/checks/constant_field.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison)

[Tested engine 109a7355ed85](https://github.com/Eidosoma/Cells/commit/109a7355ed85ff2e1e5a9c884c32801c07a2fd72) · [Evidence checkpoint 627c376c463a](https://github.com/Eidosoma/Cells/commit/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd)

## Biological evidence

**Open.** Signed transfer rate of the same ion in a cell pair with the endpoint conditions exchanged.

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
