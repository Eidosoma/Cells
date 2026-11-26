<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Permuting the formula units of a bath recipe preserves its exact dose

Each species’ target is the original amount plus the fixed bath volume times the signed sum of its contributions from the formula units. Permuting those contributions preserves the exact target, including a small residual after cancellation.

## Assumptions

- The two definitions contain the same formula-unit counts, offsets, starting amount and bath volume. Only the order of the entries changes.
- In the tests, the solute is neutral, the bath volume is 1 pL, and every input and count-times-offset product is exactly representable in float64. The independently calculated net dose is a binary fraction.

## Lean proof

**Proved**

- [CellsProofs.Tissue.BathSchedule.recipe_order](../CellsProofs/Tissue/BathSchedule.lean#L42)
- [CellsProofs.Tissue.BathSchedule.recipe_residual](../CellsProofs/Tissue/BathSchedule.lean#L49)

Direct proof subject `cells.operator.scheduled_bath_composition@1`

Uses [A held bath can return to its original composition after supplying solute and work to tissue](scheduled-bath-exchange.md)

## Numerical comparison

**Checked.** After the accurate-sum fix, both orders delivered the intended dose in all six checked worlds. Opposing contributions of ±24 mM preserved the 1.7763568394002505 × 10⁻¹⁵ fmol trace dose. The all-six-order regression passed. The earlier checkpoint records the ordering that erased the dose.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_bath_composition@1`

[Sum of each species' formula-unit contributions](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/bath_schedule.py#L230) · [All six trace-recipe orders](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/tests/unit/test_bath_schedule.py#L404) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/bath_schedule.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#bath-order-repair)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_bath_composition@1`

[Integer charge check on formula units](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L164) · [Accumulation of the per-species offsets](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L229) · [Absolute target construction](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L286) · [Application and booking of the target](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L456) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/checks/bath_schedule.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/PROGRESS.md#bath-recipe-order)

[Tested engine 94327ec434ee](https://github.com/Eidosoma/Cells/commit/94327ec434ee49f543d2b2e046c6ddb2eaa5e902) · [Evidence checkpoint 22c5bb1c30b6](https://github.com/Eidosoma/Cells/commit/22c5bb1c30b6eb79bdcf179392853755259a57e7)

## Biological evidence

**Open.** Independently assayed final solute concentration after preparing equivalent mixtures. Sensitivity to the order of entries in an engine input can be tested directly with the same recipe.

**Unit** mM

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
