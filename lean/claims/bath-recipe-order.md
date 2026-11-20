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

Direct proof subject `cells.scheduled_bath_composition@1`

Uses [A held bath can return to its original composition after supplying solute and work to tissue](scheduled-bath-exchange.md)

## Numerical comparison

**Failed.** With ordinary offsets both orders booked 0.00048828125 fmol. With large opposing terms, one order delivered that amount and the other delivered zero. At trace concentration, ordinary opposing terms of ±24 mM likewise gave either the full trace dose or zero. All six worlds were accepted. The discrepancy was already present in the parsed target and carried through to the final held amount and dose record.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_bath_composition@1`

[Integer charge check on formula units](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L164) · [Accumulation of the per-species offsets](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L229) · [Absolute target construction](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L286) · [Application and booking of the target](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L456) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/checks/bath_schedule.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/PROGRESS.md#bath-recipe-order)

[Tested engine 94327ec434ee](https://github.com/Eidosoma/Cells/commit/94327ec434ee49f543d2b2e046c6ddb2eaa5e902) · [Evidence checkpoint 22c5bb1c30b6](https://github.com/Eidosoma/Cells/commit/22c5bb1c30b6eb79bdcf179392853755259a57e7)

## Biological evidence

**Open.** Independently assayed final solute concentration after preparing equivalent mixtures. Sensitivity to the order of entries in an engine input can be tested directly with the same recipe.

**Unit** mM

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
