<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Centering a strictly interior replacement volume preserves its water-domain membership in exact arithmetic

For any declared target strictly between the water bounds, subtracting and adding the same reference volume recovers that target. The numerical comparison tests how v2 binds a target whose float64 offset would reconstruct at the excluded lower bound.

## Assumptions

- The water volume interval is open at both endpoints. The exact theorem uses a common real-valued reference for storing and reconstructing the target.
- The admission comparison uses a single template with the slot's own species amounts. Water flow is disabled and all other inputs are held fixed.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CellReplacement.template_volume_interior](../CellsProofs/Tissue/CellReplacement.lean#L64)

Direct proof subject `cells.operator.scheduled_cell_replacement@2`

Uses [Replacement over water accounts for incoming volume and composition-dependent free energy](cell-replacement-water.md)

## Numerical comparison

**Checked.** The repaired v2 definition admitted 0.18763056296676509 pL, the first float above the strict lower bound of 0.18763056296676506 pL. It also admitted the second interior float and refused the bound itself. The binding regression verified that the adjusted offset reconstructs strictly inside. The earlier comparison records the original refusal.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_cell_replacement@2`, `cells.ideal_osmosis_linear_compliance_water@1`

[Template volume placed inside the water bounds](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/operators/cell_replacement_v2.py#L205) · [Stored volume and refusal of the uncorrected offset](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/tests/unit/test_cell_replacement_v2.py#L357) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/checks/cell_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/PROGRESS.md#claim-source-review)

[Tested engine dd085e36e9ce](https://github.com/Eidosoma/Cells/commit/dd085e36e9ced2edfed88c7194e970bd335f3ad0) · [Evidence checkpoint 8f269af4c8b7](https://github.com/Eidosoma/Cells/commit/8f269af4c8b79150020b47a86dd71da848d91714)

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_cell_replacement@2`, `cells.ideal_osmosis_linear_compliance_water@1`

[Strict declared interval](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L186) · [Template stored as an offset](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L107) · [Strict runtime water domain](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/numerics/osmotic_water.py#L96) · [Newcomer domain check during definition admission](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement.py#L510) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/checks/cell_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/PROGRESS.md#cell-replacement-volume-boundary)

[Tested engine 4638694ac13b](https://github.com/Eidosoma/Cells/commit/4638694ac13bedae5f93aa56d77cf8820e687ec1) · [Evidence checkpoint ddb723080dee](https://github.com/Eidosoma/Cells/commit/ddb723080dee6544576464afaf5314a3b95e2b06)

## Biological evidence

**Open.** Cell volume and measurement uncertainty near a physiologically justified lower bound. The boundary replay tests numerical admission.

**Unit** pL

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
