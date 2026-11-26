<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A wash at the same ion concentration must collect and supply equal amounts

For an unchanged ion in a well of positive volume, replacing a fraction of liquid with solution at the well’s concentration preserves the ion inventory. The collected amount equals the supplied amount at every fraction in exact arithmetic. The engine specifies an exact equality for the corresponding cumulative counters.

## Assumptions

- Collection and refill use the same fraction, volume, ion and concentration. Both counters start from equal values. The compiled fixture holds the well at fixed volume without any other ion transfer.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CompartmentWash.same_concentration_ion](../CellsProofs/Tissue/CompartmentWash.lean#L25)

Direct proof subject `cells.operator.scheduled_compartment_wash@1`

Proof sources [Mathlib div_mul_cancel₀ specialized in the volume identity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L291)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md)

## Numerical comparison

**Checked.** On the repaired compiled host, three half washes and three 3/7 washes kept Na, K and Cl inventories fixed. Collected and supplied counters agreed exactly at every saved row and both runs completed. At 68ab12e7 the 3/7 schedule left a chloride residual of −2.98 × 10⁻⁸ fmol and the outside-material ledger refused it.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_compartment_wash@1`

[Ion sample and refill](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/operators/wash_schedule.py#L421-L436) · [Cumulative ion counters](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/operators/wash_schedule.py#L478-L491) · [Finite well and wash definition](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/validation/tissue/wash_schedule_fixtures.py#L35-L90) · [Public runner](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/execution/runner.py#L384) · [Public unchanged-ion regression](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/tests/unit/test_wash_schedule_runs.py#L62-L92) · [Exact wash identity](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/PROGRESS.md#d272-wash-clamp-retests)

[Tested engine 2ae9ce8e5c6b](https://github.com/Eidosoma/Cells/commit/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f) · [Evidence checkpoint 841e06cd5d0e](https://github.com/Eidosoma/Cells/commit/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Sample and supply](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L301) · [Cumulative counter updates](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L364) · [Finite well and wash schedule](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/wash_schedule_fixtures.py) · [Compiled scan and host acceptance](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/execution/runner.py#L242) · [Public half-wash regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_wash_schedule_runs.py#L24) · [Wash theorem](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Fluorescein dilution inputs](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/vloemans2024_dilution.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

## Biological evidence

**Open.** Ion amounts in paired samples and refills at a matched electrolyte concentration and exchanged volume.

**Unit** fmol per ion per well

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
