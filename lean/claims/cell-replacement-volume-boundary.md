<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Centering a strictly interior replacement volume preserves its water-domain membership in exact arithmetic

For any declared target strictly between the water bounds, subtracting and adding the same reference volume recovers that target. The float64 implementation can refuse a strictly interior declaration when the reconstructed value lands on the excluded lower bound.

## Assumptions

- The water volume interval is open at both endpoints. The exact theorem uses a common real-valued reference for storing and reconstructing the target.
- The admission comparison uses a single template with the slot's own species amounts. Water flow is disabled and all other inputs are held fixed.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CellReplacement.template_volume_interior](../CellsProofs/Tissue/CellReplacement.lean#L64)

Direct proof subject `cells.scheduled_cell_replacement@2`

Uses [Replacement over water accounts for incoming volume and composition-dependent free energy](cell-replacement-water.md)

## Numerical comparison

**Failed.** At reference 0.7505222518670602 pL the target 0.18763056296676509 pL reconstructs as the strict lower bound 0.18763056296676506 pL. Definition checking refuses the first interior float. The second interior float is admitted, as is the original target if only the lower bound is relaxed by one float.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_cell_replacement@2`, `cells.ideal_osmosis_linear_compliance_water@1`

[Strict declared interval](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L186) · [Template stored as an offset](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L107) · [Strict runtime water domain](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/numerics/osmotic_water.py#L96) · [Newcomer domain check during definition admission](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement.py#L510) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/checks/cell_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/PROGRESS.md#cell-replacement-volume-boundary)

[Tested engine 4638694ac13b](https://github.com/Eidosoma/Cells/commit/4638694ac13bedae5f93aa56d77cf8820e687ec1) · [Evidence checkpoint ddb723080dee](https://github.com/Eidosoma/Cells/commit/ddb723080dee6544576464afaf5314a3b95e2b06)

## Biological evidence

**Open.** Cell volume and measurement uncertainty near a physiologically justified lower bound. The recorded refusal concerns numerical admission.

**Unit** pL

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
