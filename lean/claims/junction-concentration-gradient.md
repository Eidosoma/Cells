<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# At equal voltage, junction flux follows the concentration gradient

At equal potentials the signed flux is scale × (sender concentration − receiver concentration). A positive scale gives flow from higher to lower concentration.

## Assumptions

- The transport factor has value one at zero voltage. The scale is area × permeability × opening divided by mol/fmol. The direction claim requires a positive scale.

## Lean proof

**Proved**

- [CellsProofs.Transport.flux_zero_voltage](../CellsProofs/Transport/ConstantField.lean#L47)
- [CellsProofs.Transport.flux_down_gradient](../CellsProofs/Transport/ConstantField.lean#L52)

Direct proof subject `cells.route.constant_field@1`

## Numerical comparison

**Checked.** The equal-voltage CPU fixture exercised concentration differences of both signs and compared the signed flux with an independent scalar calculation.

**Engine** `resolved_pump_tissue@3`, `constant_field@1`

[Junction flux](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/junctions/selective.py#L19) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/electrochemistry.py#L17) · [Flux booking](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/numerics/surface_transport.py#L318) · [Surface comparisons](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_transport.py#L103) · [Per-cell tissue ledger](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_pump_v3_imex.py#L80) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/checks/constant_field.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison)

[Tested engine 109a7355ed85](https://github.com/Eidosoma/Cells/commit/109a7355ed85ff2e1e5a9c884c32801c07a2fd72) · [Evidence checkpoint 627c376c463a](https://github.com/Eidosoma/Cells/commit/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd)

## Biological evidence

**Open.** Ion transfer across a junction at equal potentials and a measured concentration difference.

Near zero junction voltage, a charged tracer moved from the loaded cell to its neighbor. A separate study estimated 226 ± 75 calcein molecules/s per Cx26 channel at a 125 μM gradient, with only the donor voltage-clamped during transfer. [Palacios-Prado and Bukauskas, Fig. 2B](https://pmc.ncbi.nlm.nih.gov/articles/PMC2736430/) · [Zonta et al., Fig. 1A–C](https://doi.org/10.1186/1478-811X-11-15)

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
