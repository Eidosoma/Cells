<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A wash at the same ion concentration must collect and supply equal amounts

For an unchanged ion in a well of positive volume, replacing a fraction of liquid with solution at the well’s concentration preserves the ion inventory. The collected amount equals the supplied amount at every fraction in exact arithmetic. The engine specifies an exact equality for the corresponding cumulative counters.

## Assumptions

- Collection and refill use the same fraction, volume, ion and concentration. Both counters start from equal values. The compiled fixture holds the well at fixed volume without any other ion transfer.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CompartmentWash.same_concentration_ion](../CellsProofs/Tissue/CompartmentWash.lean#L23)

Direct proof subject `cells.scheduled_compartment_wash@1`

Proof sources [Mathlib div_mul_cancel₀ specialized in the volume identity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L291)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md)

## Numerical comparison

**Failed.** On compiled CPU float64, three 1/2 washes completed with identical counters. Three 3/7 washes kept all ionic inventories fixed. The final chloride collected minus supplied was −2.9802322387695312 × 10⁻⁸ fmol in the production scan, and the public runner refused the outside-material ledger. Sodium and potassium closed exactly.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Sample and supply](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L301) · [Cumulative counter updates](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L364) · [Finite well and wash schedule](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/wash_schedule_fixtures.py) · [Compiled scan and host acceptance](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/execution/runner.py#L242) · [Public half-wash regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_wash_schedule_runs.py#L24) · [Wash theorem](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Fluorescein dilution inputs](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/vloemans2024_dilution.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

## Biological evidence

**Open.** Ion amounts in paired samples and refills at a matched electrolyte concentration and exchanged volume.

**Unit** fmol per ion per well

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
